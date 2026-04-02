#!/bin/bash
# Tail logs from all services on the DGX
ssh dgx "cd ~/kutana-ai && docker compose logs -f"
