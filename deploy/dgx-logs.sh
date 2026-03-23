#!/bin/bash
# Tail logs from all services on the DGX
ssh dgx "cd ~/convene-ai && docker compose logs -f"
