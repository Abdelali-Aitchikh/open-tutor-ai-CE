#!/usr/bin/env python3
import sys
import os
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import main

# Example physics questions
EXAMPLES = {
    "kinematics_1": "A car accelerates uniformly from rest to a speed of 20 m/s in 10 seconds. Find the acceleration and the distance covered.",
    "kinematics_2": "A ball is thrown vertically upwards with a velocity of 20 m/s. What is the maximum height reached by the ball? (Take g = 10 m/s^2)",
    "newtons_law_1": "A block of mass 5 kg is pulled by a horizontal force of 20 N. If the coefficient of kinetic friction is 0.2, find the acceleration of the block. (Take g = 10 m/s^2)"
}

def run_example(example_name):
    """Run PhysicsVideoAgent on a specific example."""
    if example_name not in EXAMPLES:
        print(f"Example '{example_name}' not found. Available examples: {', '.join(EXAMPLES.keys())}")
        return
    
    question = EXAMPLES[example_name]
    
    print(f"Running PhysicsVideoAgent for: {example_name}")
    print(f"Question: {question}")
    print("=" * 80)
    
    # Create output directory for this example
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", example_name)
    os.makedirs(output_dir, exist_ok=True)
    
    result = main(question, output_dir)
    
    # Save the result
    with open(os.path.join(output_dir, "result.json"), "w") as f:
        json.dump(result, f, indent=2)
    
    if result["success"]:
        print(f"Successfully created explanation video: {result['final_video']}")
    else:
        print(f"Failed to create explanation video: {result['error']}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        example_name = sys.argv[1]
        run_example(example_name)
    else:
        print("Please provide an example name to run.")
        print(f"Available examples: {', '.join(EXAMPLES.keys())}")

def run_example(example_name):
    """Run TheoremExplainAgent on a specific example."""
    if example_name not in EXAMPLES:
        print(f"Example '{example_name}' not found. Available examples: {', '.join(EXAMPLES.keys())}")
        return
    
    theorem_name = example_name
    theorem_description = EXAMPLES[example_name]
    
    print(f"Running TheoremExplainAgent for: {theorem_name}")
    print(f"Description: {theorem_description}")
    print("=" * 80)
    
    # Create output directory for this example
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", theorem_name.replace(" ", "_"))
    os.makedirs(output_dir, exist_ok=True)
    
    result = main(theorem_name, theorem_description, output_dir)
    
    # Save the result
    with open(os.path.join(output_dir, "result.json"), "w") as f:
        json.dump(result, f, indent=2)
    
    if result["success"]:
        print(f"Successfully created explanation video: {result['final_video']}")
    else:
        print(f"Failed to create explanation video: {result['error']}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run TheoremExplainAgent examples")
    parser.add_argument("example", choices=list(EXAMPLES.keys()) + ["all"], help="Example to run, or 'all' for all examples")
    
    args = parser.parse_args()
    
    if args.example == "all":
        for example in EXAMPLES:
            run_example(example)
    else:
        run_example(args.example)