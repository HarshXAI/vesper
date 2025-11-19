#!/bin/bash

# VESPER Setup Verification Script
# Checks that everything is configured correctly

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         VESPER Setup Verification                   ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

CHECKS_PASSED=0
CHECKS_TOTAL=0

check() {
    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
    if eval "$1" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $2"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $2"
        if [ -n "$3" ]; then
            echo -e "  ${YELLOW}→${NC} $3"
        fi
        return 1
    fi
}

echo -e "${BLUE}Prerequisites:${NC}"
check "command -v docker" "Docker installed" "Install from https://docs.docker.com/get-docker/"
check "command -v docker-compose" "Docker Compose installed" "Usually comes with Docker Desktop"
check "command -v python3" "Python 3 installed" "Install from https://www.python.org/downloads/"
check "command -v git" "Git installed" "Install from https://git-scm.com/downloads"
check "command -v make" "Make installed" "Usually pre-installed on macOS/Linux"

echo ""
echo -e "${BLUE}Project Structure:${NC}"
check "[ -f README.md ]" "README.md exists"
check "[ -f docker-compose.yml ]" "docker-compose.yml exists"
check "[ -f Makefile ]" "Makefile exists"
check "[ -f .env.example ]" ".env.example exists"
check "[ -f .gitignore ]" ".gitignore exists"
check "[ -d services ]" "services/ directory exists"
check "[ -d infrastructure ]" "infrastructure/ directory exists"
check "[ -d docs ]" "docs/ directory exists"
check "[ -d scripts ]" "scripts/ directory exists"

echo ""
echo -e "${BLUE}Configuration Files:${NC}"
check "[ -f SETUP.md ]" "SETUP.md exists"
check "[ -f CONTRIBUTING.md ]" "CONTRIBUTING.md exists"
check "[ -f PROJECT_STATUS.md ]" "PROJECT_STATUS.md exists"
check "[ -f QUICKSTART.md ]" "QUICKSTART.md exists"
check "[ -f LICENSE ]" "LICENSE exists"

echo ""
echo -e "${BLUE}Scripts:${NC}"
check "[ -x scripts/setup-local.sh ]" "setup-local.sh is executable"
check "[ -x scripts/test-unit.sh ]" "test-unit.sh is executable"
check "[ -x scripts/build-and-push.sh ]" "build-and-push.sh is executable"

echo ""
echo -e "${BLUE}Infrastructure:${NC}"
check "[ -f infrastructure/terraform/environments/dev/main.tf ]" "Terraform dev environment exists"
check "[ -f infrastructure/terraform/environments/dev/variables.tf ]" "Terraform variables exist"
check "[ -d infrastructure/terraform/modules/networking ]" "Networking module exists"

echo ""
echo -e "${BLUE}Documentation:${NC}"
check "[ -f docs/README.md ]" "Documentation index exists"
check "[ -f docs/architecture/system-overview.md ]" "Architecture docs exist"

echo ""
echo -e "${BLUE}Docker Services:${NC}"
if [ -f docker-compose.yml ]; then
    services=$(grep -E '^\s+[a-z-]+:$' docker-compose.yml | grep -v '^#' | wc -l | tr -d ' ')
    echo -e "${GREEN}✓${NC} $services services configured in docker-compose.yml"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
else
    echo -e "${RED}✗${NC} docker-compose.yml not found"
fi
CHECKS_TOTAL=$((CHECKS_TOTAL + 1))

echo ""
echo -e "${BLUE}Environment:${NC}"
if [ -f .env ]; then
    echo -e "${GREEN}✓${NC} .env file exists"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
else
    echo -e "${YELLOW}!${NC} .env file not found (run 'make setup' to create)"
fi
CHECKS_TOTAL=$((CHECKS_TOTAL + 1))

echo ""
echo "═══════════════════════════════════════════════════════"
echo ""

if [ $CHECKS_PASSED -eq $CHECKS_TOTAL ]; then
    echo -e "${GREEN}✓ All checks passed! ($CHECKS_PASSED/$CHECKS_TOTAL)${NC}"
    echo ""
    echo -e "${GREEN}Your VESPER setup is complete and ready to use!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review .env configuration: vim .env"
    echo "  2. Start services: make start"
    echo "  3. Check health: make health"
    echo "  4. View docs: cat QUICKSTART.md"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some checks failed ($CHECKS_PASSED/$CHECKS_TOTAL passed)${NC}"
    echo ""
    echo "Please address the issues above before proceeding."
    echo "Run 'make setup' to create missing files."
    echo ""
    exit 1
fi
