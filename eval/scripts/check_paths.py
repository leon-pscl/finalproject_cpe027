import os, sys
from pathlib import Path

def check(name, path_str):
    p = Path(path_str)
    print(f'{name}: {p} -> {"exists" if p.exists() else "MISSING"}')

if __name__ == '__main__':
    datasets = {
        'ACL': r'E:\Datasets\(ACL6060)2023.iwslt-1.2.dataset',
        'Loquacious_dev': r'E:\Datasets\loquacious\dev',
        'Loquacious_test': r'E:\Datasets\loquacious\test',
        'M3AV': r'E:\Datasets\M3AV',
        'DEMAND': r'E:\Datasets\DEMAND',
        'MUSAN': r'E:\Datasets\MUSAN',
    }
    for n, p in datasets.items():
        check(n, p)
