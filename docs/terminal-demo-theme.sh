#!/usr/bin/env bash
# TraceLoc terminal demo theme (Bash/Zsh compatible)

# Core palette
export TRACELOC_BG="#0B1020"
export TRACELOC_CYAN="#00E5FF"
export TRACELOC_GREEN="#00FFA3"
export TRACELOC_TEXT="#EAF2FF"
export TRACELOC_MUTED="#8BA2C7"

# ANSI shortcuts
export TL_RESET='\[\e[0m\]'
export TL_CYAN='\[\e[96m\]'
export TL_GREEN='\[\e[92m\]'
export TL_BLUE='\[\e[94m\]'
export TL_GRAY='\[\e[90m\]'

# Prompt: user@host path + traceloc marker
export PS1="${TL_CYAN}┌─${TL_GREEN}[TraceLoc]${TL_RESET} ${TL_BLUE}\u@\h ${TL_GRAY}\w${TL_RESET}\n${TL_CYAN}└─▶ ${TL_RESET}"

# Helpful aliases for demos
alias tl-help='python3 traceloc.py --help'
alias tl-phone='python3 traceloc.py -p +14155552671 --format human'
alias tl-addr='python3 traceloc.py -a "1600 Amphitheatre Parkway, Mountain View, CA" --format json'
alias tl-mix='python3 traceloc.py -f input.txt --format human'

echo "[TraceLoc] terminal demo theme loaded."
