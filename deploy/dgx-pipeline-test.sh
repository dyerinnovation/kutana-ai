#!/bin/bash
# Run the pipeline test on the DGX
ssh jondyer3@spark-b0f2.local "cd ~/convene-ai && python3 examples/test-pipeline.py"
