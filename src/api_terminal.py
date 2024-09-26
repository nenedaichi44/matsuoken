from openai import OpenAI

client = OpenAI()

settings = {
    "model": "gpt-4o",
    "temperature": 0,
    # ... more settings
}


response = client.chat.completions.create(
    messages=[
        {
            "content": "あなたは優秀はQAシステムです。ユーザーからの質問に対して、Step by Stepで思考して適切な回答を返してください",
            "role": "system"
        },
        {
            "content": input(),
            "role": "user"
        }
    ],
    **settings
)

print(response.choices[0].message.content)