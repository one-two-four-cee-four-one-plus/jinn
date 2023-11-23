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
