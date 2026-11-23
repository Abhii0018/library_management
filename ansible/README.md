# DevOps Automation with Ansible for LibriCore

This directory contains the **Ansible Configuration Management & Application Deployment** suite for the **LibriCore Library Management System**, aligned with the **LPU DevOps Syllabus (Unit V & Unit VI)**.

---

## 1. Syllabus Concepts Covered

| Syllabus Topic (Unit V & VI) | Implementation in LibriCore |
| :--- | :--- |
| **Inventory File** (`inventory.ini`) | Defines the target server (`localhost`), connection type (`local`), and deployment variables. |
| **Configuration File** (`ansible.cfg`) | Sets default inventory, output formatting, and host key checking. |
| **Playbook Structure** (`deploy.yml`) | Standard multi-task YAML structure defining hosts, variables, tasks, and handlers. |
| **Pip Module** | Automated dependency installation from `requirements.txt`. |
| **Command / Shell Modules** | Runs Django database migrations, admin initialization, and test suites. |
| **Handlers** | Event-driven trigger (`notify: Notify Dependencies Installed`). |
| **Tags** | Allows running selective tasks (`--tags migrate`, `--tags test`, `--tags deps`). |
| **Facts & Debug Module** | Captures host OS details and displays formatted deployment summaries. |

---

## 2. How to Run the Playbook

From the project root:

```bash
# 1. Activate Virtual Environment
source venv/bin/activate

# 2. Run the Full Deployment Playbook
ansible-playbook -i ansible/inventory.ini ansible/deploy.yml
```

### Running Selective Steps with Tags:
```bash
# Run only database migrations
ansible-playbook -i ansible/inventory.ini ansible/deploy.yml --tags migrate

# Run only automated test verification
ansible-playbook -i ansible/inventory.ini ansible/deploy.yml --tags test

# Run only dependency check
ansible-playbook -i ansible/inventory.ini ansible/deploy.yml --tags deps
```

---

## 3. What to Say in Your Viva / Teacher Presentation

> *"Sir, for the DevOps component of our syllabus (Units V & VI), I implemented an **Ansible Application Deployment Playbook**.*  
> *Instead of manually installing dependencies, configuring environments, running migrations, and launching tests on every server, Ansible provides **agentless, declarative automation**.*  
> *With a single command (`ansible-playbook deploy.yml`), Ansible reads our inventory, validates system prerequisites, applies database schemas, provisions the admin account, and executes our 55 automated tests to guarantee zero-downtime deployment."*
