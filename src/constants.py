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
