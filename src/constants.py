OPENAI_FUNCTION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "[Name of the function]",
        "description": "[Description of function]",
        "parameters": {
            "type": "object",
            "properties": {
                "[property name]": {
                    "type": "[property type]",
                    "description": "[property description]"
                },
                "[other property name]": {
                    "type": "[other property type]",
                    "description": "[other property description]"
                }
                },
            "required": [
                ["[property name]", "[other property name]"]
            ]
        }
    }
}
CRAFT_INCANTATION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "craft_incantation",
        "description": (
            "This function creates a new external tool matching definition in natural language and adds it to"
            " the list of known tools for further use."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Tool definition in natural language"
                }
            },
            "required": [
                "text"
            ]
        }
    }
}

CSS = '''
/* Apply the Iosevka font to the whole document */
body {
    font-family: 'Iosevka', monospace;
    background-color: #f5f5f5;
    color: #333333;
    margin: 0;
    padding: 20px;
}

/* Style for forms and inputs */
input, textarea, select, button {
    font-family: inherit;
    padding: 10px;
    margin: 10px 0;
    border: none;
    border-bottom: 2px solid black;
    background-color: transparent;
}

input:focus, textarea:focus, select:focus, button:focus {
    outline: none;
    border-bottom-color: #000;
}

/* Style for URLs */
a {
    color: #000;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

/* Style for UL/LI lists */
ul {
    list-style-type: none;
    padding: 0;
}

li {
    margin-bottom: 10px;
    padding-left: 16px;
    position: relative;
}

li::before {
    content: '';
    position: absolute;
    left: 0;
    top: 50%;
    height: 8px;
    width: 8px;
    background-color: black;
    border-radius: 50%;
    transform: translateY(-50%);
}

/* Additional Styles */
button {
    background-color: black;
    color: white;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.3s;
}

button:hover {
    background-color: #333;
}

/* Style for details and summary */
details {
    border: 1px solid #000;
    padding: 10px;
    margin-bottom: 10px;
    background-color: #f9f9f9;
}

summary {
    font-weight: bold;
    cursor: pointer;
    list-style: none;
    display: block;
    text-decoration: none;
}

summary::-webkit-details-marker {
    display: none;
}

details[open] summary {
    border-bottom: 1px solid #000;
}

/* Style for preformatted text */
pre {
    background-color: #f9f9f9;
    border-left: 3px solid #000;
    padding: 10px;
    overflow-x: auto;
    font-family: 'Iosevka', monospace;
    font-size: 0.9em;
    margin-bottom: 10px;
    white-space: pre-wrap; /* wrap text in case of long lines */
}

/* Style for textarea */
textarea {
    font-family: 'Iosevka', monospace;
    width: 100%;
    padding: 10px;
    margin: 10px 0;
    border: 1px solid #000;
    border-radius: 0; /* Makes edges solid and not rounded */
    background-color: transparent;
    resize: vertical; /* Allows vertical resizing only */
    box-sizing: border-box; /* Includes padding and border in the element's total width and height */
}

textarea:focus {
    outline: none;
    border-color: #333;
}
'''
