#!/bin/bash

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

if ! command -v isort >/dev/null 2>&1; then
    echo -e "${RED}Error: isort is not installed${NC}"
    exit 1
fi

if ! command -v ruff >/dev/null 2>&1; then
    echo -e "${RED}Error: ruff is not installed${NC}"
    exit 1
fi

echo -e "${BLUE}Checking for staged Python files...${NC}"

FILES=$(git diff --cached --name-only --diff-filter=ACM | grep "\.py$" || true)

if [ -z "$FILES" ]; then
    echo -e "${YELLOW}No Python files staged for commit${NC}"
    exit 0
fi

echo -e "${BLUE}Found staged Python files:${NC}"
echo -e "${YELLOW}$FILES${NC}\n"

echo -e "${BLUE}Checking isort...${NC}"
echo -e "${BLUE}Attempting to fix import sorting...${NC}"
isort $FILES
if ! isort --check-only $FILES; then
    echo -e "${RED}isort check failed${NC}"
    exit 1
fi
echo -e "${GREEN}isort check passed${NC}\n"

echo -e "${BLUE}Checking ruff...${NC}"
if ! ruff check $FILES; then
    echo -e "${RED}ruff check failed${NC}"
    exit 1
fi
echo -e "${GREEN}ruff check passed${NC}\n"

echo -e "${GREEN}All checks passed successfully${NC}"