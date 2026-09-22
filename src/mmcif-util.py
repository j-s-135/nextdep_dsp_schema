from wwpdb.io.file.mmCIFUtil import mmCIFUtil
import argparse
import pprint

def main():
    parser = argparse.ArgumentParser(description='Extracts the experimental method from a mmCIF file.')
    parser.add_argument('-f', '--mmcif_file', help='Path to the mmCIF file', required=True)
    parser.add_argument('-o', '--output_file', help='Path to the output file (optional)')
    parser.add_argument('--categories', action='store_true', help='Show available categories')
    parser.add_argument('--attributes', help='Show attributes for a specific category (provide category name)')
    parser.add_argument('--category', help='Show attributes for a specific category (provide category name)')
    args = parser.parse_args()

    if args.categories and args.category:
        print("Please specify either --categories or --category, not both.")
        return

    mmcif_util = mmCIFUtil(filePath=args.mmcif_file)

    if args.categories:
        result = mmcif_util.GetCategories()
        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(pprint.pformat(result))
        else:
            pprint.pprint(f"Available categories: {result}")
    elif args.attributes:
        result = mmcif_util.GetAttributes(args.attributes)
        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(pprint.pformat(result))
        else:
            pprint.pprint(f"Attributes for category '{args.category}': {result}")
    elif args.category:
        result = mmcif_util.GetValue(args.category)
        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(pprint.pformat(result))
        else:
            pprint.pprint(f"Category '{args.category}': {result}")

if __name__ == '__main__':
    main()