import json

# Load the JSON file
with open('prompts.json', 'r') as file:
    data = json.load(file)

# Remove escape characters
for item in data:
    if 'prompt' in item:
        item['prompt'] = item['prompt'].replace('\n', '').replace('\t', '')

# Save the modified JSON file
with open('prompts.json', 'w') as file:
    json.dump(data, file, indent=4)
