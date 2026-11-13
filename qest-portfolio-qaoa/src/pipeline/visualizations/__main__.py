import argparse

from . import generate_report


def main():
    parser = argparse.ArgumentParser(
        description="Generate the extended QAOA portfolio visualization suite.")
    parser.add_argument("--all", action="store_true",
                        help="Generate all light plots (data + results + quantum + network).")
    parser.add_argument("--data", action="store_true", help="Data-level plots only.")
    parser.add_argument("--results", action="store_true", help="Results-level plots only.")
    parser.add_argument("--quantum", action="store_true",
                        help="Quantum plots only (circuit diagram + sampled distribution).")
    parser.add_argument("--network", action="store_true", help="Include the correlation network.")
    parser.add_argument("--landscape", action="store_true",
                        help="Include the heavy 3D energy landscape.")
    parser.add_argument("--file", type=str, default=None,
                        help="Specific results CSV (default: richest results/logs file).")
    parser.add_argument("--data-dir", type=str, default="data/raw")
    parser.add_argument("--output-dir", type=str, default="results/visualisations")
    parser.add_argument("--grid-points", type=int, default=20)
    parser.add_argument("--maxiter", type=int, default=60)
    args = parser.parse_args()

    explicit = args.data or args.results or args.quantum or args.network or args.landscape
    run_all = args.all or not explicit

    generate_report(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        results_csv=args.file,
        do_data=run_all or args.data,
        do_results=run_all or args.results,
        do_quantum=run_all or args.quantum,
        include_network=run_all or args.network,
        include_landscape=args.landscape,
        grid_points=args.grid_points,
        maxiter=args.maxiter,
    )


if __name__ == "__main__":
    main()
