#!/bin/bash
# Tail logs from all services on the DGX
ssh jondyer3@spark-b0f2.local "cd ~/convene-ai && docker compose logs -f"
