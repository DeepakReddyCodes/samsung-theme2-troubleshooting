import argparse
import sys

def calculate_cost(input_tokens_per_req, output_tokens_per_req, requests_per_month, price_per_1m_input, price_per_1m_output, cache_hit_rate=0.0):
    # Uncached scenario
    uncached_input_cost = (input_tokens_per_req / 1_000_000) * price_per_1m_input
    uncached_output_cost = (output_tokens_per_req / 1_000_000) * price_per_1m_output
    uncached_cost_per_query = uncached_input_cost + uncached_output_cost

    uncached_monthly_cost = uncached_cost_per_query * requests_per_month

    # Cached scenario (assume cache hit uses 0 API tokens for simplicity in this baseline model)
    # The cache cost itself is operational, but for LLM API cost:
    cached_requests = requests_per_month * cache_hit_rate
    uncached_requests = requests_per_month * (1.0 - cache_hit_rate)

    cached_cost_per_query = uncached_cost_per_query * (1.0 - cache_hit_rate) # average effective cost

    total_monthly_cost_with_cache = (uncached_requests * uncached_cost_per_query)

    return {
        "uncached_cost_per_query": uncached_cost_per_query,
        "cached_effective_cost_per_query": cached_cost_per_query,
        "uncached_monthly_cost": uncached_monthly_cost,
        "monthly_cost_with_cache": total_monthly_cost_with_cache,
        "monthly_savings_with_cache": uncached_monthly_cost - total_monthly_cost_with_cache
    }

def main():
    parser = argparse.ArgumentParser(description="Parameterized Cost Calculator for LLM Troubleshooting Engine")
    parser.add_argument("--input-tokens", type=int, default=1000, help="Average input tokens per request")
    parser.add_argument("--output-tokens", type=int, default=300, help="Average output tokens per request")
    parser.add_argument("--requests", type=int, default=100000, help="Estimated requests per month")
    parser.add_argument("--price-input", type=float, default=0.15, help="Price per 1M input tokens (e.g. Gemini Flash or GPT-4o-mini)")
    parser.add_argument("--price-output", type=float, default=0.60, help="Price per 1M output tokens")
    parser.add_argument("--cache-hit-rate", type=float, default=0.85, help="Expected cache hit rate (0.0 to 1.0)")

    args = parser.parse_args()

    result = calculate_cost(
        args.input_tokens,
        args.output_tokens,
        args.requests,
        args.price_input,
        args.price_output,
        args.cache_hit_rate
    )

    print("==================================================")
    print("             COST CALCULATOR RESULTS              ")
    print("==================================================")
    print(f"Parameters:")
    print(f"  Input Tokens / Request : {args.input_tokens}")
    print(f"  Output Tokens / Request: {args.output_tokens}")
    print(f"  Monthly Requests       : {args.requests:,}")
    print(f"  Provider Input Price   : ${args.price_input} / 1M tokens")
    print(f"  Provider Output Price  : ${args.price_output} / 1M tokens")
    print(f"  Expected Cache Hit Rate: {args.cache_hit_rate * 100:.1f}%")
    print("-" * 50)
    print("Estimates:")
    print(f"  Estimated Uncached Cost/Query : ${result['uncached_cost_per_query']:.6f}")
    print(f"  Estimated Cached Cost/Query   : ${result['cached_effective_cost_per_query']:.6f} (effective avg)")
    print("-" * 50)
    print("Projections (Monthly Scenario):")
    print(f"  Monthly Cost (No Cache)       : ${result['uncached_monthly_cost']:,.2f}")
    print(f"  Monthly Cost (With Cache)     : ${result['monthly_cost_with_cache']:,.2f}")
    print(f"  Monthly Savings via Cache     : ${result['monthly_savings_with_cache']:,.2f}")
    print("==================================================")

if __name__ == "__main__":
    main()
