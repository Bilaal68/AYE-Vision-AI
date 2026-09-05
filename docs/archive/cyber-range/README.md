# Cyber Range - Isolated Adversary Simulation Environment

The Cyber Range is an isolated testing environment for executing adversary emulations, attack simulations, and detection rule validation.

> [!CAUTION]
> **Network Isolation Rule**: The Cyber Range runs on its own isolated Docker network (`cyberrange_net`). It must **NEVER** be connected to or bridged with `secint_net` (the main platform stack network).

## Folder Structure
- `vulnerable-services/`: Intentionally vulnerable web applications and services for penetration testing and attack scenario execution.
- `detection-tests/`: Attack automation scripts, PCAP files, and detection rule validation payloads.
- `docker-compose.cyberrange.yml`: Separate Docker Compose file for orchestrating Cyber Range targets.

## Running the Cyber Range

To start the isolated Cyber Range environment:
```bash
docker compose -f docker-compose.cyberrange.yml up -d
```

To stop the environment:
```bash
docker compose -f docker-compose.cyberrange.yml down
```
