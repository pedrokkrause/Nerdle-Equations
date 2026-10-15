#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cmath>
#include <algorithm>
#include <chrono>
#include <iomanip>
#include <unordered_map>
#include <cstdint>
#include <random>

#ifdef _OPENMP
#include <omp.h>
#endif

constexpr int MAX_PATTERNS = 6561; // 3^8 possible patterns for length 8

// Computes Wordle/Nerdle feedback: 2=Green, 1=Yellow, 0=Gray
inline uint16_t compute_feedback(const std::string& guess, const std::string& secret, int len) {
    uint8_t res[16] = {0};
    uint8_t unmatched[128] = {0};

    // Pass 1: Exact matches
    for (int i = 0; i < len; ++i) {
        if (guess[i] == secret[i]) {
            res[i] = 2;
        } else {
            unmatched[static_cast<unsigned char>(secret[i])]++;
        }
    }

    // Pass 2: Misplaced matches
    for (int i = 0; i < len; ++i) {
        if (res[i] == 0) {
            unsigned char c = guess[i];
            if (unmatched[c] > 0) {
                res[i] = 1;
                unmatched[c]--;
            }
        }
    }

    uint16_t pat = 0;
    for (int i = 0; i < len; ++i) {
        pat = pat * 3 + res[i];
    }
    return pat;
}

// Low-overhead histogram for entropy calculations (resets in O(touched))
struct FastHistogram {
    int counts[MAX_PATTERNS] = {0};
    uint16_t touched[MAX_PATTERNS];
    int touched_count = 0;

    inline void add(uint16_t pat) {
        if (counts[pat] == 0) {
            touched[touched_count++] = pat;
        }
        counts[pat]++;
    }

    inline void clear() {
        for (int i = 0; i < touched_count; ++i) {
            counts[touched[i]] = 0;
        }
        touched_count = 0;
    }
};

struct CandScore {
    double entropy;
    uint16_t idx;
    int lb;
};

struct ThreadWorkspace {
    FastHistogram hist;
    std::unordered_map<uint64_t, int> memo;
    std::vector<std::pair<uint16_t, uint16_t>> pair_buf;
    std::vector<CandScore> score_buf;
    std::vector<uint8_t> is_cand_buf;

    void init(int n_words) {
        memo.reserve(1 << 16);
        score_buf.reserve(n_words);
        is_cand_buf.assign(n_words, 0);
    }
};

class NerdleOptimizer {
public:
    int n_words = 0;
    int word_len = 8;
    int exact_pattern = 0;
    int n_max = 10;
    std::vector<std::string> words;

    // Flat feedback matrix (628 MB for 17,723 words)
    std::vector<uint16_t> matrix;
    std::vector<int> lb_table;
    std::vector<uint64_t> zobrist_table;
    std::vector<double> n_log_n_table; // Fast O(1) entropy lookup

    NerdleOptimizer(const std::vector<std::string>& wordlist, int n_max_param = 10)
            : words(wordlist), n_max(n_max_param) {
        n_words = words.size();
        word_len = words[0].length();

        exact_pattern = 0;
        for (int i = 0; i < word_len; ++i) exact_pattern = exact_pattern * 3 + 2;

        init_tables();
        init_matrix();
    }

    void init_tables() {
        // Precompute lower bounds
        lb_table.assign(n_words + 1, 0);
        int curr_k = 0, depth = 1;
        long long cap = 1;
        int max_p = std::pow(3, word_len);

        while (curr_k < n_words) {
            int fill = std::min<long long>(cap, n_words - curr_k);
            for (int i = 0; i < fill; ++i) {
                curr_k++;
                lb_table[curr_k] = lb_table[curr_k - 1] + depth;
            }
            depth++;
            cap = (depth == 2) ? (max_p - 1) : (cap * max_p);
        }

        // Precompute Zobrist keys
        std::mt19937_64 rng(1337);
        zobrist_table.resize(n_words);
        for (int i = 0; i < n_words; ++i) {
            zobrist_table[i] = rng();
        }

        // Precompute n * log2(n) table to eliminate runtime transcendental math
        n_log_n_table.assign(n_words + 1, 0.0);
        for (int i = 1; i <= n_words; ++i) {
            n_log_n_table[i] = i * std::log2(static_cast<double>(i));
        }
    }

    void init_matrix() {
        size_t total_elements = static_cast<size_t>(n_words) * n_words;
        size_t mem_mb = (total_elements * sizeof(uint16_t)) / (1024 * 1024);
        std::cout << "Allocating and precomputing feedback matrix (" << mem_mb << " MB)..." << std::endl;

        auto t0 = std::chrono::high_resolution_clock::now();
        matrix.resize(total_elements);

#pragma omp parallel for schedule(dynamic, 64)
        for (int g = 0; g < n_words; ++g) {
            size_t row_offset = static_cast<size_t>(g) * n_words;
            for (int s = 0; s < n_words; ++s) {
                matrix[row_offset + s] = compute_feedback(words[g], words[s], word_len);
            }
        }

        auto t1 = std::chrono::high_resolution_clock::now();
        double elapsed = std::chrono::duration<double>(t1 - t0).count();
        std::cout << "Matrix ready in " << std::fixed << std::setprecision(2) << elapsed << "s.\n";
    }

    uint64_t compute_hash(const std::vector<uint16_t>& candidates) const {
        uint64_t h = 0;
        for (uint16_t c : candidates) h ^= zobrist_table[c];
        return h;
    }

    // Rank all equations in the dataset by initial Shannon entropy
    std::vector<std::pair<double, uint16_t>> rank_all_by_initial_entropy() {
        std::cout << "Scoring initial Shannon entropy across all " << n_words << " equations...\n";
        std::vector<std::pair<double, uint16_t>> initial_scores(n_words);
        double log_n = std::log2(n_words);

#pragma omp parallel
        {
            FastHistogram hist;
#pragma omp for schedule(static)
            for (int g = 0; g < n_words; ++g) {
                hist.clear();
                size_t row = static_cast<size_t>(g) * n_words;
                for (int s = 0; s < n_words; ++s) {
                    hist.add(matrix[row + s]);
                }

                double sum_s_log_s = 0.0;
                for (int i = 0; i < hist.touched_count; ++i) {
                    sum_s_log_s += n_log_n_table[hist.counts[hist.touched[i]]];
                }
                double ent = log_n - (sum_s_log_s / n_words);
                initial_scores[g] = {ent, static_cast<uint16_t>(g)};
            }
        }

        std::sort(initial_scores.begin(), initial_scores.end(),
                  [](const auto& a, const auto& b) { return a.first > b.first; });
        return initial_scores;
    }

    inline int solve_size_3(size_t s0, size_t s1, size_t s2) const {
        if (matrix[s0 * n_words + s1] != matrix[s0 * n_words + s2]) return 5;
        if (matrix[s1 * n_words + s0] != matrix[s1 * n_words + s2]) return 5;
        if (matrix[s2 * n_words + s0] != matrix[s2 * n_words + s1]) return 5;
        return 6;
    }

    int solve_tree(const std::vector<uint16_t>& S, ThreadWorkspace& ws) {
        int k = static_cast<int>(S.size());
        if (k <= 1) return k;
        if (k == 2) return 3;
        if (k == 3) return solve_size_3(S[0], S[1], S[2]);

        uint64_t hash = compute_hash(S);
        auto it = ws.memo.find(hash);
        if (it != ws.memo.end()) return it->second;

        int best_cost = 1e9;
        double log_k = std::log2(k);
        ws.score_buf.clear();

        // =====================================================================
        // STAGE 1: Test in-pool candidates (g in S) first in O(k^2)
        // =====================================================================
        for (uint16_t g : S) {
            ws.is_cand_buf[g] = 1;
            ws.hist.clear();
            size_t row = static_cast<size_t>(g) * n_words;
            for (uint16_t s : S) {
                ws.hist.add(matrix[row + s]);
            }

            // 1. Perfect in-pool split: 2*k - 1 is the global theoretical minimum
            if (ws.hist.touched_count == k) {
                for (uint16_t s : S) ws.is_cand_buf[s] = 0;
                ws.memo[hash] = 2 * k - 1;
                return 2 * k - 1;
            }

            // 2. Pigeonhole Principle: k items in k-1 buckets with g in exact_pattern
            //    means 1 bucket of size 2 and k-2 buckets of size 1 -> exact cost 2*k
            if (ws.hist.touched_count == k - 1) {
                best_cost = 2 * k;
                continue;
            }

            double sum_s_log_s = 0.0;
            int max_b = 0;
            for (int i = 0; i < ws.hist.touched_count; ++i) {
                int c = ws.hist.counts[ws.hist.touched[i]];
                sum_s_log_s += n_log_n_table[c];
                if (c > max_b) max_b = c;
            }

            int lb = (k <= MAX_PATTERNS) ? (3 * k - 1 - ws.hist.touched_count) : k;
            if (max_b <= 2) {
                best_cost = std::min(best_cost, lb);
                continue; // Exact cost already recorded in best_cost!
            }

            double ent = log_k - (sum_s_log_s / k) + 1e-6;
            ws.score_buf.push_back({ent, g, lb});
        }

        // If any in-pool guess achieved 2*k, no out-of-pool guess can beat it (min external is 2*k)!
        if (best_cost == 2 * k) {
            for (uint16_t s : S) ws.is_cand_buf[s] = 0;
            ws.memo[hash] = 2 * k;
            return 2 * k;
        }

        // =====================================================================
        // STAGE 2: Scan out-of-pool words (g not in S)
        // =====================================================================
        for (int g = 0; g < n_words; ++g) {
            if (ws.is_cand_buf[g]) continue;

            ws.hist.clear();
            size_t row = static_cast<size_t>(g) * n_words;
            for (uint16_t s : S) {
                ws.hist.add(matrix[row + s]);
            }

            if (ws.hist.touched_count <= 1) continue;

            // Since Stage 1 proved 2*k - 1 is impossible, 2*k is now the global minimum!
            if (ws.hist.touched_count == k) {
                for (uint16_t s : S) ws.is_cand_buf[s] = 0;
                ws.memo[hash] = 2 * k;
                return 2 * k;
            }

            int lb = (k <= MAX_PATTERNS) ? (3 * k - ws.hist.touched_count) : k;
            if (lb >= best_cost) continue; // Prune BEFORE pushing to score_buf!

            double sum_s_log_s = 0.0;
            int max_b = 0;
            for (int i = 0; i < ws.hist.touched_count; ++i) {
                int c = ws.hist.counts[ws.hist.touched[i]];
                sum_s_log_s += n_log_n_table[c];
                if (c > max_b) max_b = c;
            }

            if (max_b <= 2) {
                best_cost = std::min(best_cost, lb);
                continue; // Exact cost already recorded!
            }

            double ent = log_k - (sum_s_log_s / k);
            ws.score_buf.push_back({ent, static_cast<uint16_t>(g), lb});
        }

        for (uint16_t s : S) ws.is_cand_buf[s] = 0;

        int num_avail = static_cast<int>(ws.score_buf.size());
        int num_to_branch = std::min(num_avail, n_max);
        if (num_to_branch < num_avail) {
            std::partial_sort(ws.score_buf.begin(), ws.score_buf.begin() + num_to_branch, ws.score_buf.end(),
                              [](const auto& a, const auto& b) { return a.entropy > b.entropy; });
        } else {
            std::sort(ws.score_buf.begin(), ws.score_buf.end(),
                      [](const auto& a, const auto& b) { return a.entropy > b.entropy; });
        }

        // Copy out the top candidates for this depth level (since recursion reuses ws.score_buf)
        std::vector<CandScore> branch_guesses(ws.score_buf.begin(), ws.score_buf.begin() + num_to_branch);

        // =====================================================================
        // STAGE 3: Branch-and-Bound over surviving candidates
        // =====================================================================
        for (const auto& cand : branch_guesses) {
            // Instant O(1) prune BEFORE touching pair_buf or allocating sub_buckets!
            if (cand.lb >= best_cost) continue;

            uint16_t g = cand.idx;
            size_t row = static_cast<size_t>(g) * n_words;

            ws.pair_buf.resize(k);
            for (int i = 0; i < k; ++i) {
                ws.pair_buf[i] = {matrix[row + S[i]], S[i]};
            }
            std::sort(ws.pair_buf.begin(), ws.pair_buf.end(),
                      [](const auto& a, const auto& b) { return a.first < b.first; });

            // Start with cand.lb (which already includes k + exact costs of b=1,2 + 2b-1 for b>=3)
            int curr_cost = cand.lb;
            std::vector<std::vector<uint16_t>> sub_buckets;
            int i = 0;

            while (i < k) {
                uint16_t pat = ws.pair_buf[i].first;
                int j = i + 1;
                while (j < k && ws.pair_buf[j].first == pat) ++j;
                int b = j - i;

                if (b >= 3 && pat != exact_pattern) {
                    if (b == 3) {
                        // Solve b=3 inline with zero heap allocation!
                        curr_cost += solve_size_3(ws.pair_buf[i].second,
                                                  ws.pair_buf[i + 1].second,
                                                  ws.pair_buf[i + 2].second) - 5;
                        if (curr_cost >= best_cost) break;
                    } else {
                        sub_buckets.emplace_back(b);
                        for (int m = 0; m < b; ++m) {
                            sub_buckets.back()[m] = ws.pair_buf[i + m].second;
                        }
                    }
                }
                i = j;
            }

            if (curr_cost >= best_cost) continue;

            std::sort(sub_buckets.begin(), sub_buckets.end(),
                      [](const auto& a, const auto& b) { return a.size() > b.size(); });

            bool pruned = false;
            for (const auto& sb : sub_buckets) {
                int b = static_cast<int>(sb.size());
                int sub_lb = 2 * b - 1;
                int sub_cost = solve_tree(sb, ws);
                curr_cost += (sub_cost - sub_lb);

                if (curr_cost >= best_cost) {
                    pruned = true;
                    break;
                }
            }

            if (!pruned && curr_cost < best_cost) {
                best_cost = curr_cost;
                if (best_cost <= 2 * k) break; // Cannot possibly beat 2*k at Stage 3
            }
        }

        ws.memo[hash] = best_cost;
        return best_cost;
    }

    // Benchmark an opener by parallelizing decision-tree evaluation over all its buckets
    double evaluate_opener(uint16_t opener_idx) {
        size_t row = static_cast<size_t>(opener_idx) * n_words;

        // Partition the full dictionary
        std::unordered_map<uint16_t, std::vector<uint16_t>> root_buckets;
        for (int s = 0; s < n_words; ++s) {
            uint16_t pat = matrix[row + s];
            if (pat != exact_pattern) {
                root_buckets[pat].push_back(s);
            }
        }

        std::vector<std::vector<uint16_t>> bucket_list;
        bucket_list.reserve(root_buckets.size());
        for (auto& [_, subset] : root_buckets) {
            bucket_list.push_back(std::move(subset));
        }

        // Sort descending so the largest sub-trees start first across threads
        std::sort(bucket_list.begin(), bucket_list.end(),
                  [](const auto& a, const auto& b) { return a.size() > b.size(); });

        long long total_guess_sum = n_words; // Turn 1 cost for all secrets

#pragma omp parallel reduction(+:total_guess_sum)
        {
            ThreadWorkspace ws;
            ws.init(n_words);

#pragma omp for schedule(dynamic, 1)
            for (size_t b = 0; b < bucket_list.size(); ++b) {
                total_guess_sum += solve_tree(bucket_list[b], ws);
            }
        }

        return static_cast<double>(total_guess_sum) / n_words;
    }
};

int main(int argc, char* argv[]) {
    std::string filename = (argc > 1) ? argv[1] : "classic_equations.txt";
    int n_max = (argc > 2) ? std::stoi(argv[2]) : 1000000;
    int top_n_openers_to_test = (argc > 3) ? std::stoi(argv[3]) : 20;

    std::vector<std::string> words;
    std::ifstream infile(filename);
    if (!infile.is_open()) {
        std::cerr << "Error: Could not open wordlist file '" << filename << "'.\n";
        return 1;
    }

    std::string line;
    int expected_len = -1;
    while (std::getline(infile, line)) {
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ' || line.back() == '\t')) {
            line.pop_back();
        }
        if (line.empty()) continue;

        if (expected_len == -1) {
            expected_len = line.length();
        } else if (static_cast<int>(line.length()) != expected_len) {
            std::cerr << "Error: Inconsistent word length in file. Expected "
                      << expected_len << ", but got '" << line << "' (" << line.length() << " chars).\n";
            return 1;
        }
        words.push_back(line);
    }

    if (words.empty()) {
        std::cerr << "Error: Wordlist file is empty.\n";
        return 1;
    }

    std::cout << "Successfully loaded " << words.size() << " equations (length "
              << expected_len << ") from " << filename << ".\n";

    NerdleOptimizer optimizer(words, n_max);

    // Step 1: Rank all equations by initial Shannon entropy
    auto ranked_openers = optimizer.rank_all_by_initial_entropy();

    std::cout << "\n=======================================================\n";
    std::cout << " TOP " << top_n_openers_to_test << " OPENERS BY SHANNON ENTROPY\n";
    std::cout << " (Evaluating decision trees with N_max = " << n_max
              << ", bypassing entropy when |S| < " << n_max << ")\n";
    std::cout << "=======================================================\n";

    struct Result {
        std::string word;
        double entropy;
        double avg_guesses;
        double time_sec;
    };
    std::vector<Result> results;

    std::string best_word = "";
    double best_avg = 1e9;

    for (int i = 0; i < top_n_openers_to_test; ++i) {
        uint16_t opener_idx = ranked_openers[i].second;
        std::string word = optimizer.words[opener_idx];
        double entropy = ranked_openers[i].first;

        std::cout << "\n[" << (i + 1) << "/" << top_n_openers_to_test << "] Evaluating opener '"
                  << word << "' (Entropy: " << std::fixed << std::setprecision(4) << entropy << " bits)..." << std::flush;

        auto t0 = std::chrono::high_resolution_clock::now();
        double avg_guesses = optimizer.evaluate_opener(opener_idx);
        auto t1 = std::chrono::high_resolution_clock::now();
        double elapsed = std::chrono::duration<double>(t1 - t0).count();

        std::cout << " Done in " << std::fixed << std::setprecision(2) << elapsed
                  << "s -> Expected Average Turns: " << std::setprecision(4) << avg_guesses << "\n";

        results.push_back({word, entropy, avg_guesses, elapsed});

        if (avg_guesses < best_avg) {
            best_avg = avg_guesses;
            best_word = word;
        }
    }

    // Step 2: Final Leaderboard
    std::sort(results.begin(), results.end(), [](const auto& a, const auto& b) {
        return a.avg_guesses < b.avg_guesses;
    });

    std::cout << "\n=======================================================\n";
    std::cout << "                 FINAL LEADERBOARD\n";
    std::cout << "=======================================================\n";
    std::cout << std::left << std::setw(6) << "Rank"
              << std::setw(12) << "Equation"
              << std::setw(16) << "Entropy (bits)"
              << std::setw(18) << "Average Turns"
              << std::setw(12) << "Compute Time" << "\n";
    std::cout << "-------------------------------------------------------\n";

    for (size_t i = 0; i < results.size(); ++i) {
        std::cout << std::left << std::setw(6) << (i + 1)
                  << std::setw(12) << results[i].word
                  << std::setw(16) << std::fixed << std::setprecision(4) << results[i].entropy
                  << std::setw(18) << std::fixed << std::setprecision(4) << results[i].avg_guesses
                  << std::setw(10) << std::fixed << std::setprecision(2) << results[i].time_sec << "s\n";
    }

    std::cout << "=======================================================\n";
    std::cout << "🏆 BEST FIRST GUESS: " << best_word
              << " (" << std::fixed << std::setprecision(4) << best_avg << " average turns)\n";
    std::cout << "=======================================================\n";

    return 0;
}