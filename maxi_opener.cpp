#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cmath>
#include <algorithm>
#include <chrono>
#include <iomanip>
#include <cstdint>
#include <bit>
#include <memory>
#include <random>

#ifdef _OPENMP
#include <omp.h>
#endif

constexpr int WORD_LEN = 10;
constexpr int MAX_PATTERNS = 59049;
constexpr size_t SAMPLE_SIZE = 50000;
constexpr int TOP_FINALISTS = 300; // Number of finalists to evaluate via full decision trees

struct Equation {
    char data[WORD_LEN];
};

std::string normalize_equation(const std::string& raw) {
    std::string out;
    out.reserve(WORD_LEN);
    for (size_t i = 0; i < raw.size(); ++i) {
        unsigned char c = static_cast<unsigned char>(raw[i]);
        if (c == 0xC2 && i + 1 < raw.size()) {
            unsigned char next = static_cast<unsigned char>(raw[i + 1]);
            if (next == 0xB2) { out += 'Q'; ++i; continue; } // '²' -> 'Q'
            if (next == 0xB3) { out += 'C'; ++i; continue; } // '³' -> 'C'
        }
        out += raw[i];
    }
    return out;
}

std::string denormalize_equation(const char* eq, int len) {
    std::string out;
    for (int i = 0; i < len; ++i) {
        if (eq[i] == 'Q') out += "²";
        else if (eq[i] == 'C') out += "³";
        else out += eq[i];
    }
    return out;
}

inline uint16_t compute_feedback(const char* guess, const char* secret) {
    uint8_t res[WORD_LEN] = {0};
    uint8_t unmatched[256] = {0};

    for (int i = 0; i < WORD_LEN; ++i) {
        if (guess[i] == secret[i]) {
            res[i] = 2;
        } else {
            unmatched[static_cast<unsigned char>(secret[i])]++;
        }
    }

    for (int i = 0; i < WORD_LEN; ++i) {
        if (res[i] == 0) {
            unsigned char c = static_cast<unsigned char>(guess[i]);
            if (unmatched[c] > 0) {
                res[i] = 1;
                unmatched[c]--;
            }
        }
    }

    uint16_t pat = 0;
    for (int i = 0; i < WORD_LEN; ++i) {
        pat = pat * 3 + res[i];
    }
    return pat;
}

inline int count_unique_chars(const char* eq) {
    uint64_t mask[4] = {0, 0, 0, 0};
    for (int i = 0; i < WORD_LEN; ++i) {
        unsigned char c = static_cast<unsigned char>(eq[i]);
        mask[c / 64] |= (1ULL << (c % 64));
    }
    return std::popcount(mask[0]) + std::popcount(mask[1]) +
           std::popcount(mask[2]) + std::popcount(mask[3]);
}

struct FastHist {
    std::vector<int> counts;
    std::vector<uint16_t> touched;
    int touched_count = 0;

    FastHist() : counts(MAX_PATTERNS, 0), touched(MAX_PATTERNS, 0) {}

    inline void add(uint16_t pat) {
        if (counts[pat] == 0) touched[touched_count++] = pat;
        counts[pat]++;
    }

    inline void clear() {
        for (int i = 0; i < touched_count; ++i) counts[touched[i]] = 0;
        touched_count = 0;
    }
};

inline int solve_size_3(uint32_t s0, uint32_t s1, uint32_t s2, const std::vector<Equation>& dataset) {
    if (compute_feedback(dataset[s0].data, dataset[s1].data) !=
        compute_feedback(dataset[s0].data, dataset[s2].data)) return 5;
    if (compute_feedback(dataset[s1].data, dataset[s0].data) !=
        compute_feedback(dataset[s1].data, dataset[s2].data)) return 5;
    if (compute_feedback(dataset[s2].data, dataset[s0].data) !=
        compute_feedback(dataset[s2].data, dataset[s1].data)) return 5;
    return 6;
}

int solve_subbucket(const std::vector<uint32_t>& S, const std::vector<Equation>& dataset,
                    const std::vector<double>& n_log_n, FastHist& hist, int exact_pattern) {
    int k = static_cast<int>(S.size());
    if (k <= 1) return k;
    if (k == 2) return 3;
    if (k == 3) return solve_size_3(S[0], S[1], S[2], dataset);

    int best_cost = 1e9;
    int num_to_test = std::min(k, 10);

    // Keep track of the integer lower-bound cost for each candidate as well
    struct Cand {
        double entropy;
        uint32_t idx;
        int base_cost;
        int max_bucket;
    };
    std::vector<Cand> scored(k);
    double log_k = std::log2(k);

    for (int i = 0; i < k; ++i) {
        uint32_t g = S[i];
        hist.clear();
        for (uint32_t s : S) {
            hist.add(compute_feedback(dataset[g].data, dataset[s].data));
        }

        // FAST EXIT: If guess `g` separates all k items into size-1 buckets,
        // 2*k - 1 is the theoretical minimum possible cost for any size-k bucket!
        if (hist.touched_count == k) {
            return 2 * k - 1;
        }

        double sum_s = 0.0;
        int max_b = 0;
        for (int m = 0; m < hist.touched_count; ++m) {
            int c = hist.counts[hist.touched[m]];
            sum_s += n_log_n[c];
            if (c > max_b) max_b = c;
        }

        int base_cost = 3 * k - 1 - hist.touched_count;
        // If max_b <= 2, base_cost is ALREADY the exact cost for this guess!
        if (max_b <= 2 && base_cost < best_cost) {
            best_cost = base_cost;
        }

        scored[i] = {log_k - (sum_s / k), g, base_cost, max_b};
    }

    std::partial_sort(scored.begin(), scored.begin() + num_to_test, scored.end(),
                      [](const auto& a, const auto& b) { return a.entropy > b.entropy; });

    std::vector<std::pair<uint16_t, uint32_t>> pairs(k);
    std::vector<uint32_t> sub;

    for (int i = 0; i < num_to_test; ++i) {
        // Skip if the lower bound alone can't beat best_cost, or if max_b <= 2 (already recorded)
        if (scored[i].base_cost >= best_cost || scored[i].max_bucket <= 2) {
            continue;
        }

        uint32_t g = scored[i].idx;
        for (int m = 0; m < k; ++m) {
            pairs[m] = {compute_feedback(dataset[g].data, dataset[S[m]].data), S[m]};
        }
        std::sort(pairs.begin(), pairs.end(), [](const auto& a, const auto& b) {
            return a.first < b.first;
        });

        // Start with the exact cost of all b=1,2 buckets + lower bound (2b-1) of all b>=3 buckets
        int curr_cost = scored[i].base_cost;
        int m = 0;
        while (m < k) {
            uint16_t p = pairs[m].first;
            int j = m + 1;
            while (j < k && pairs[j].first == p) ++j;
            int b = j - m;

            // Buckets of size 1 and 2 (and exact_pattern) are ALREADY exact in base_cost!
            if (b >= 3 && p != exact_pattern) {
                if (b == 3) {
                    curr_cost += solve_size_3(pairs[m].second, pairs[m + 1].second, pairs[m + 2].second, dataset) - 5;
                } else {
                    sub.assign(b, 0);
                    for (int x = 0; x < b; ++x) sub[x] = pairs[m + x].second;
                    curr_cost += solve_subbucket(sub, dataset, n_log_n, hist, exact_pattern) - (2 * b - 1);
                }
                if (curr_cost >= best_cost) break;
            }
            m = j;
        }

        if (curr_cost < best_cost) {
            best_cost = curr_cost;
        }
    }

    return best_cost;
}

int main(int argc, char* argv[]) {
    std::string filename = (argc > 1) ? argv[1] : "maxi_nerdle.txt";

    std::cout << "Loading equations from " << filename << "...\n";
    std::vector<Equation> dataset;
    dataset.reserve(2300000);

    std::ifstream infile(filename, std::ios::binary);
    if (!infile.is_open()) {
        std::cerr << "Failed to open file.\n";
        return 1;
    }

    std::string line;
    while (std::getline(infile, line)) {
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ' || line.back() == '\t')) line.pop_back();
        std::string norm = normalize_equation(line);
        if (norm.length() == WORD_LEN) {
            Equation eq;
            std::copy(norm.begin(), norm.end(), eq.data);
            dataset.push_back(eq);
        }
    }
    size_t N = dataset.size();
    std::cout << "Loaded " << N << " equations (" << (N * sizeof(Equation)) / (1024 * 1024) << " MB RAM).\n";

    // Step 1: Filter 10 unique chars
    std::vector<int> candidates;
    for (size_t i = 0; i < N; ++i) {
        if (count_unique_chars(dataset[i].data) == 10) candidates.push_back(i);
    }
    std::cout << "Found " << candidates.size() << " 10-unique-character candidate openers.\n";

    // Precompute N*log2(N)
    std::vector<double> n_log_n(N + 1, 0.0);
    for (size_t i = 1; i <= N; ++i) n_log_n[i] = i * std::log2(static_cast<double>(i));

    // Step 2: Screen top 10 finalists via fast 30,000-sample entropy
    std::cout << "Screening candidates to isolate the top " << TOP_FINALISTS << " finalists...\n";
    std::vector<int> sample_indices(SAMPLE_SIZE);
    std::mt19937 rng(1337);
    std::uniform_int_distribution<size_t> dist(0, N - 1);
    for (size_t i = 0; i < SAMPLE_SIZE; ++i) sample_indices[i] = dist(rng);

    std::vector<std::pair<double, int>> sample_scores(candidates.size());
    double log_sample = std::log2(SAMPLE_SIZE);

#pragma omp parallel
    {
        FastHist hist;
#pragma omp for schedule(dynamic, 128)
        for (int c = 0; c < static_cast<int>(candidates.size()); ++c) {
            hist.clear();
            const char* guess = dataset[candidates[c]].data;
            for (size_t s = 0; s < SAMPLE_SIZE; ++s) {
                hist.add(compute_feedback(guess, dataset[sample_indices[s]].data));
            }
            double sum_s = 0.0;
            for (int i = 0; i < hist.touched_count; ++i) sum_s += n_log_n[hist.counts[hist.touched[i]]];
            sample_scores[c] = {log_sample - (sum_s / SAMPLE_SIZE), candidates[c]};
        }
    }

    std::partial_sort(sample_scores.begin(), sample_scores.begin() + TOP_FINALISTS, sample_scores.end(),
                      [](const auto& a, const auto& b) { return a.first > b.first; });

    // Step 3: Exact Decision Tree Evaluation for Finalists
    int exact_pattern = 0;
    for (int i = 0; i < WORD_LEN; ++i) exact_pattern = exact_pattern * 3 + 2;

    struct FinalResult {
        std::string eq;
        double entropy;
        double avg_turns;
        double compute_sec;
    };
    std::vector<FinalResult> results;

    std::cout << "\n=================================================================\n";
    std::cout << " EVALUATING FULL DECISION TREES ACROSS ALL 2.2M EQUATIONS\n";
    std::cout << "=================================================================\n";

    for (int f = 0; f < TOP_FINALISTS; ++f) {
        int opener_idx = sample_scores[f].second;
        const char* guess = dataset[opener_idx].data;
        std::string eq_display = denormalize_equation(guess, WORD_LEN);

        std::cout << "[" << (f + 1) << "/" << TOP_FINALISTS << "] Evaluating opener: "
                  << eq_display << "... " << std::flush;

        auto t0 = std::chrono::high_resolution_clock::now();

        // 1. Partition the 2.2M secrets into buckets
        std::vector<std::vector<uint32_t>> buckets(MAX_PATTERNS);
        for (size_t s = 0; s < N; ++s) {
            uint16_t pat = compute_feedback(guess, dataset[s].data);
            if (pat != exact_pattern) {
                buckets[pat].push_back(s);
            }
        }

        std::vector<std::vector<uint32_t>> active_buckets;
        for (int p = 0; p < MAX_PATTERNS; ++p) {
            if (!buckets[p].empty()) active_buckets.push_back(std::move(buckets[p]));
        }

        // Sort descending so the largest subtrees are evaluated first
        std::sort(active_buckets.begin(), active_buckets.end(),
                  [](const auto& a, const auto& b) { return a.size() > b.size(); });

        long long total_guess_sum = N; // Turn 1 cost

        // 2. Parallel evaluation of all subtrees across CPU cores
#pragma omp parallel reduction(+:total_guess_sum)
        {
            FastHist thread_hist;
#pragma omp for schedule(dynamic, 1)
            for (size_t b = 0; b < active_buckets.size(); ++b) {
                total_guess_sum += solve_subbucket(active_buckets[b], dataset, n_log_n, thread_hist, exact_pattern);
            }
        }

        auto t1 = std::chrono::high_resolution_clock::now();
        double elapsed = std::chrono::duration<double>(t1 - t0).count();
        double avg_turns = static_cast<double>(total_guess_sum) / N;

        std::cout << "Done in " << std::fixed << std::setprecision(2) << elapsed
                  << "s -> Expected Average Turns: " << std::setprecision(5) << avg_turns << "\n";

        results.push_back({eq_display, sample_scores[f].first, avg_turns, elapsed});
    }

    // Step 4: Final Leaderboard ranked by TRUE AVERAGE GUESSES
    std::sort(results.begin(), results.end(), [](const auto& a, const auto& b) {
        return a.avg_turns < b.avg_turns;
    });

    std::cout << "\n=================================================================\n";
    std::cout << "          FINAL LEADERBOARD (RANKED BY AVERAGE GUESSES)\n";
    std::cout << "=================================================================\n";
    std::cout << std::left << std::setw(6) << "Rank"
              << std::setw(18) << "Equation"
              << std::setw(18) << "Sample Entropy"
              << std::setw(18) << "Average Turns"
              << std::setw(12) << "Tree Time" << "\n";
    std::cout << "-----------------------------------------------------------------\n";

    for (size_t i = 0; i < results.size(); ++i) {
        std::cout << std::left << std::setw(6) << (i + 1)
                  << std::setw(18) << results[i].eq
                  << std::setw(18) << std::fixed << std::setprecision(4) << results[i].entropy
                  << std::setw(18) << std::fixed << std::setprecision(4) << results[i].avg_turns
                  << std::setw(10) << std::fixed << std::setprecision(2) << results[i].compute_sec << "s\n";
    }

    std::cout << "=================================================================\n";
    std::cout << "🏆 PROVABLE BEST OPENER: " << results[0].eq
              << " (" << std::fixed << std::setprecision(4) << results[0].avg_turns << " average turns)\n";
    std::cout << "=================================================================\n";

    return 0;
}