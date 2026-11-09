import argparse
import json
from pathlib import Path
from . import evaluate, markdown

def main():
    parser = argparse.ArgumentParser(description='Replay read-only Uniswap v4 quote regression fixtures')
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, default=Path('report'))
    args = parser.parse_args()
    try:
        if args.input.stat().st_size > 1_000_000:
            raise ValueError('Input exceeds 1 MB')
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('Duplicate JSON key')
                result[key] = value
            return result
        result = evaluate(json.loads(args.input.read_text(), object_pairs_hook=unique))
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
        (args.output / 'report.md').write_text(markdown(result))
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, f'Input rejected: {error}\n')
    print(json.dumps({'passed': result['passed'], 'routes': len(result['routes']), 'receipt': str(args.output / 'receipt.json')}))
    return 0 if result['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
