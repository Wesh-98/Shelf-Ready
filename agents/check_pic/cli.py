"""
Check-Pic Command Line Interface

Standalone CLI for running image quality control analysis.

Usage:
    python -m agents.CheckPic.cli --in image.jpg --work_on image
    python -m agents.CheckPic.cli --in_dir ./images --report qc_report.json
    python -m agents.CheckPic.cli --in image.jpg --verbose
"""

import argparse
import json
import os
import sys
from typing import List

from .agent import CheckPicAgent
from .config import CheckPicConfig
from .models import QCResult


def main():
    parser = argparse.ArgumentParser(
        description="Check-Pic Image Quality Control Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Analyze single image:
    python -m agents.CheckPic.cli --in product.jpg

  Analyze with canvas mode:
    python -m agents.CheckPic.cli --in product.jpg --work_on canvas

  Analyze directory:
    python -m agents.CheckPic.cli --in_dir ./images --report results.json

  Verbose output:
    python -m agents.CheckPic.cli --in product.jpg --verbose
        """
    )

    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--in", dest="in_path",
        help="Single image file to analyze"
    )
    input_group.add_argument(
        "--in_dir", dest="in_dir",
        help="Directory of images to analyze"
    )

    # Analysis options
    parser.add_argument(
        "--work_on", choices=["image", "canvas"], default="image",
        help="Analysis mode: 'image' for raw products, 'canvas' for placed products"
    )
    parser.add_argument(
        "--intended_size", type=int, default=1500,
        help="Expected output canvas size in pixels"
    )
    parser.add_argument(
        "--fit_mode", choices=["pad", "fit", "crop_fill"], default="pad",
        help="Expected fit mode"
    )

    # Output options
    parser.add_argument(
        "--report", dest="report_path",
        help="Output report file path (.json or .txt)"
    )
    parser.add_argument(
        "--format", choices=["json", "text", "brief"], default="text",
        help="Output format"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show detailed output including metrics"
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="Show summary statistics (for directory analysis)"
    )

    # Filter options
    parser.add_argument(
        "--min_severity", choices=["info", "warning", "error", "critical"],
        default="info",
        help="Minimum severity level to report"
    )
    parser.add_argument(
        "--recursive", "-r", action="store_true", default=True,
        help="Recurse into subdirectories"
    )

    args = parser.parse_args()

    # Initialize agent
    agent = CheckPicAgent()

    # Build context
    context = {
        "intended_size": args.intended_size,
        "fit_mode": args.fit_mode
    }

    results: List[QCResult] = []

    # Single file analysis
    if args.in_path:
        if not os.path.exists(args.in_path):
            print(f"Error: File not found: {args.in_path}", file=sys.stderr)
            sys.exit(1)

        result = agent.analyze_file(args.in_path, args.work_on, **context)
        results.append(result)

    # Directory analysis
    elif args.in_dir:
        if not os.path.isdir(args.in_dir):
            print(f"Error: Directory not found: {args.in_dir}", file=sys.stderr)
            sys.exit(1)

        print(f"Analyzing images in: {args.in_dir}", file=sys.stderr)
        results = agent.analyze_directory(
            args.in_dir,
            args.work_on,
            recursive=args.recursive,
            **context
        )
        print(f"Analyzed {len(results)} images", file=sys.stderr)

    # Output results
    if args.format == "json":
        output = {
            "results": [r.to_dict() for r in results]
        }
        if args.summary and len(results) > 1:
            output["summary"] = agent.get_summary(results)

        json_str = json.dumps(output, indent=2)

        if args.report_path:
            with open(args.report_path, "w") as f:
                f.write(json_str)
            print(f"Report saved to: {args.report_path}", file=sys.stderr)
        else:
            print(json_str)

    elif args.format == "text":
        for result in results:
            print(result.to_text(verbose=args.verbose))
            print("-" * 60)

        if args.summary and len(results) > 1:
            summary = agent.get_summary(results)
            print("\n=== SUMMARY ===")
            print(f"Total images: {summary['total_images']}")
            print(f"Passed: {summary['passed']} ({summary['pass_rate']}%)")
            print(f"Failed: {summary['failed']}")
            print(f"Average score: {summary['average_score']}")
            print(f"\nTop issues:")
            for code, count in summary['top_issues']:
                print(f"  {code}: {count}")

        if args.report_path:
            with open(args.report_path, "w") as f:
                for result in results:
                    f.write(result.to_text(verbose=args.verbose))
                    f.write("\n" + "-" * 60 + "\n")
            print(f"Report saved to: {args.report_path}", file=sys.stderr)

    elif args.format == "brief":
        for result in results:
            status = "PASS" if result.passed else "FAIL"
            score = result.metrics.get("overall_score", 0)
            issues = len(result.issues)
            print(f"{status} [{score:.0f}] {result.source_path} ({issues} issues)")

    # Exit code based on results
    if any(not r.passed for r in results):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
