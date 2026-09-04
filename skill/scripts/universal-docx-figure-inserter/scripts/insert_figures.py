#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Universal Docx Figure Inserter (CLI Wrapper)
Usage: python3 insert_figures.py --docx input.docx --assets-dir ./assets --output final.docx
"""
import argparse
from inserter_v2 import UniversalInserter

def main():
    parser = argparse.ArgumentParser(description="Universal Docx Figure Inserter")
    parser.add_argument("--docx", required=True, help="Input Word document")
    parser.add_argument("--assets-dir", required=True, help="Assets directory")
    parser.add_argument("--output", required=True, help="Output path")
    parser.add_argument("--font", default="宋体", help="Font for captions")
    parser.add_argument("--img-width", type=float, default=15.0, help="Image width in cm")
    
    args = parser.parse_args()
    
    config = {
        "Font": args.font,
        "Figure": {"MaxWidthCm": args.img_width, "FontSizePt": 10.5, "Bold": True, "CaptionPos": "Below"}
    }
    
    inserter = UniversalInserter(args.docx, args.assets_dir, args.output, config=config)
    report = inserter.run()
    
    print("\n--- Insertion Report ---")
    print(f"Success: {len(report['success'])}")
    print(f"Failed:  {len(report['failed'])}")
    print(f"Missing: {len(report['missing'])}")
    
    if report['missing']:
        print("\nMissing items:")
        for m in report['missing']:
            print(f"  - {m['type']} {m['id']}: {m['title']}")

if __name__ == "__main__":
    main()
