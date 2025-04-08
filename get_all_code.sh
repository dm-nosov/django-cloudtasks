#!/bin/bash

# Create output file
output_file="all_code.text"
rm -f "$output_file"
touch "$output_file"

# Function to process a file
process_file() {
  local file=$1
  echo -e "\n\n# ===============================================" >> "$output_file"
  echo -e "# FILE: $file" >> "$output_file"
  echo -e "# ===============================================\n" >> "$output_file"
  cat "$file" >> "$output_file"
}

# Main python files in the project (excluding venv)
for file in $(find . -name "*.py" -not -path "*/venv/*" -not -path "*/__pycache__/*"); do
  process_file "$file"
done

echo "All Python code has been compiled into $output_file"