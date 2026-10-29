# Wrapper script to execute the ASR benchmark

# Import the benchmark function from the package
from eval.harness.run_benchmark import run_benchmark

if __name__ == "__main__":
    # Adjust `model_path` here if your ASR checkpoint is elsewhere
    # Example: run_benchmark(model_path="C:/path/to/your/model.pt")
    run_benchmark()
