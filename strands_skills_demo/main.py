from strands import Agent
from strands.models.openai import OpenAIModel  # 使用 OpenAI 兼容接口
from strands.agent.conversation_manager import SummarizingConversationManager,SlidingWindowConversationManager
from strands_tools import file_read, shell, editor,file_write,tavily
import json
import os
import asyncio
import argparse
from skill_tool import generate_skill_tool,SkillToolInterceptor 
from ask_user_tool import ask_user
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
os.environ['BYPASS_TOOL_CONSENT'] = "true"

ROOT = Path(__file__).parent
WORK_ROOT = Path(__file__).parent / "workdir"
print(f"work dir: {WORK_ROOT}")
try:
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
except PermissionError:
    print(f"Error: No permission to create directory at {WORK_ROOT}")
    raise
except Exception as e:
    print(f"Error creating work directory: {e}")
    raise

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "dummy-key")
LLM_MODEL_ID = os.environ.get("LLM_MODEL_ID", "gpt-5")
LLM_SUMMARY_MODEL_ID = os.environ.get("LLM_SUMMARY_MODEL_ID", "gpt-5")

print(f"🔗 模型网关: {LLM_BASE_URL}")
print(f"🤖 主模型: {LLM_MODEL_ID}")
print(f"📝 摘要模型: {LLM_SUMMARY_MODEL_ID}")

# Agent Configuration
agent_model = OpenAIModel(
    model_id=LLM_MODEL_ID,
    client_args={
        "base_url": LLM_BASE_URL,
        "api_key": LLM_API_KEY,
    },
    params={
        "temperature": 1,
        "max_tokens": 24000,
    }
)

# Create a cheaper, faster model for summarization tasks
summarization_model = OpenAIModel(
    model_id=LLM_SUMMARY_MODEL_ID,
    client_args={
        "base_url": LLM_BASE_URL,
        "api_key": LLM_API_KEY,
    },
    params={
        "max_tokens": 10000,
        "temperature": 0.1,  # Low temperature for consistent summaries
    }
)

conversation_manager = SummarizingConversationManager(
    summary_ratio=0.4,
    preserve_recent_messages=20,
    summarization_agent=Agent(model=summarization_model)
)

# Dynamically create skill tools, as it should read Skills folders when agent starts.
skill_tool = generate_skill_tool()


# Create agent with MCP tools
agent = Agent(
        model=agent_model,
        system_prompt=f"""You are a helpful AI assistant with access to various skills that enhance your capabilities.
<IMPORTANT>
- Your current project root is {ROOT} and your working directory is {WORK_ROOT}, you are grant write permissions with file system (create/edit/delete etc) in the working directory {WORK_ROOT}.
Don't create files outside the working directory.    
- Use 'AskUserQuestion' tool when you need to ask the user questions during execution. 
</IMPORTANT>
""",
        tools=[file_read, shell, editor,file_write, skill_tool,ask_user,tavily],
        conversation_manager=conversation_manager,
        hooks=[SkillToolInterceptor()],
        callback_handler=None  # 禁用默认的 PrintingCallbackHandler，避免重复打印
        )


async def main(user_input_arg: str = None, messages_arg: str = None):
    # User input from command-line arguments with priority: --messages > --user-input > default
    if messages_arg is not None and messages_arg.strip():
        # Parse messages JSON and pass full conversation history to agent
        try:
            messages_list = json.loads(messages_arg)
            # Pass the full messages list to the agent
            user_input = messages_list
        except (json.JSONDecodeError, KeyError, TypeError):
            user_input = "Hello, how can you help me?"
    elif user_input_arg is not None and user_input_arg.strip():
        user_input = user_input_arg.strip()
    # Execute agent with streaming
    async for event in agent.stream_async(user_input):
        if "data" in event:
            print(event['data'],end='',flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Execute Strands Agent')
    parser.add_argument('--prompt', type=str, help='User input prompt')
    parser.add_argument('--messages', type=str, help='JSON string of conversation messages')

    args = parser.parse_args()

    user_input_param = args.prompt
    messages_param = args.messages

    asyncio.run(main(user_input_param, messages_param))