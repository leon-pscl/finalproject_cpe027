import json
import re
from pathlib import Path

def parse_version(spec: str) -> str:
    # Simplify version spec for table
    return spec.strip()

def generate_frontend_table() -> str:
    pkg_path = Path('frontend/package.json')
    data = json.loads(pkg_path.read_text())
    deps = data.get('dependencies', {})
    dev = data.get('devDependencies', {})
    rows = []
    # purpose mapping limited, use generic
    purpose_map = {
        'react': 'UI library',
        'react-dom': 'DOM rendering',
        'react-router-dom': 'Routing',
        'vite': 'Build/dev server',
        'typescript': 'TypeScript support',
        'tailwindcss': 'Utility‑first CSS',
        'autoprefixer': 'CSS vendor prefixes',
        'animejs': 'Animations',
        'lucide-react': 'Icon set',
        'eslint': 'Linting',
        'prettier': 'Code formatting',
        '@testing-library/react': 'Component testing',
        'vitest': 'Test runner',
    }
    for lib, ver in {**deps, **dev}.items():
        rows.append(f"| {lib} | {parse_version(ver)} | {purpose_map.get(lib, 'Utility')} |")
    header = "### Frontend\n| Library | Version | Purpose |\n|---|---|---|"
    return "\n".join([header] + rows)

def generate_backend_table() -> str:
    req_path = Path('backend/requirements.txt')
    rows = []
    purpose_map = {
        'fastapi': 'API framework',
        'uvicorn[standard]': 'ASGI server',
        'pydantic-settings': 'Settings management',
        'python-dotenv': '.env loading',
        'python-multipart': 'Multipart handling',
        'faster-whisper': 'Whisper ASR',
        'av': 'Audio/video handling',
        'scipy': 'Scientific computing',
        'requests': 'HTTP client',
        'httpx': 'Async HTTP client',
        'sentence-transformers': 'Embeddings',
        'torch': 'Tensor library',
        'numpy': 'Numeric arrays',
        'faiss-cpu': 'Vector store',
    }
    for line in req_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # split name and version spec
        if '>=' in line or '<' in line or '!=' in line:
            # use regex to separate name and spec
            m = re.match(r'([^>=<]+)(.*)', line)
            if m:
                name = m.group(1).strip()
                spec = m.group(2).strip()
            else:
                name, spec = line, ''
        else:
            name, spec = line, ''
        rows.append(f"| {name} | {parse_version(spec)} | {purpose_map.get(name, 'Utility')} |")
    header = "### Backend\n| Library | Version | Purpose |\n|---|---|---|"
    return "\n".join([header] + rows)

def generate_evaluation_table() -> str:
    # Evaluation dependencies are listed in eval/requirements.txt (heavy libs)
    req_path = Path('eval/requirements.txt')
    rows = []
    purpose_map = {
        'pandas': 'Data manipulation for results',
        'rapidfuzz': 'Fast string distance for WER/CER',
        'jiwer': 'Word error rate calculations',
        'pesq': 'Speech quality metric',
        'pystoi': 'Short‑time objective intelligibility',
        'torchmetrics': 'Metric utilities',
        'onnxruntime': 'DNSMOS model inference',
    }
    # Try to extract from comments or placeholder; here we just use known list
    for lib, purpose in purpose_map.items():
        rows.append(f"| {lib} | (unspecified) | {purpose} |")
    header = "### Evaluation\n| Library | Version | Purpose |\n|---|---|---|"
    return "\n".join([header] + rows)

def main():
    readme_path = Path('README.md')
    content = readme_path.read_text()
    start = '<!-- AUTO-DEP-TABLES START -->'
    end = '<!-- AUTO-DEP-TABLES END -->'
    pattern = re.compile(rf'({re.escape(start)}.*?{re.escape(end)})', re.DOTALL)
    generated = "\n".join([
        start,
        generate_frontend_table(),
        generate_backend_table(),
        generate_evaluation_table(),
        end,
    ])
    new_content = pattern.sub(generated, content)
    readme_path.write_text(new_content)
    print('README dependencies tables updated.')

if __name__ == '__main__':
    main()
