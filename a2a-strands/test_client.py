from a2a.client import A2AClient,A2ACardResolver
from typing import Any
from uuid import uuid4
from a2a.types import (
    SendMessageResponse,
    GetTaskResponse,
    SendMessageSuccessResponse,
    Task,
    TaskState,
    SendMessageRequest,
    MessageSendParams,
    GetTaskRequest,
    TaskQueryParams,
    SendStreamingMessageRequest,
)
import httpx
import traceback

AGENT_URL = "http://localhost:9000"

user_queries = [
    "what time is it now in Beijing",
    "What pricing model does Amazon Bedrock Support?",
    "How to integrate AWS Lambda with SNS?",
    "What are the IAM policies that AWS lambda should have?"
]


def create_send_message_payload(
    text: str, task_id: str | None = None, context_id: str | None = None
) -> dict[str, Any]:
    """Helper function to create the payload for sending a task."""
    payload: dict[str, Any] = {
        "message": {
            "role": "user",
            "parts": [{"type": "text", "text": text}],
            "messageId": uuid4().hex,
        },
    }

    if task_id:
        payload["message"]["taskId"] = task_id

    if context_id:
        payload["message"]["contextId"] = context_id
    return payload


def print_json_response(response: Any, description: str) -> None:
    """Helper function to print the JSON representation of a response."""
    print(f"--- {description} ---")
    if hasattr(response, "root"):
        print(f"{response.root.model_dump_json(exclude_none=True)}\n")
    else:
        print(f"{response.model_dump(mode='json', exclude_none=True)}\n")


async def run_single_turn_test(client: A2AClient) -> None:
    """Runs a single-turn non-streaming test."""

    send_payload = create_send_message_payload(text="hello, what time is it now in beijing")
    request = SendMessageRequest(id=str(uuid4()),params=MessageSendParams(**send_payload))

    print("--- Single Turn Request ---")
    # Send Message
    send_response: SendMessageResponse = await client.send_message(request)
    print_json_response(send_response, "Single Turn Request Response")
    if not isinstance(send_response.root, SendMessageSuccessResponse):
        print("received non-success response. Aborting get task ")
        return

    if not isinstance(send_response.root.result, Task):
        print("received non-task response. Aborting get task ")
        return

    task_id: str = send_response.root.result.id
    print("---Query Task---")
    # query the task
    task_id_payload = {"id": task_id}
    get_request = GetTaskRequest(params=TaskQueryParams(**task_id_payload))
    get_response: GetTaskResponse = await client.get_task(get_request)
    print_json_response(get_response, "Query Task Response")


async def run_streaming_test(client: A2AClient) -> None:
    """Runs a single-turn streaming test."""

    send_payload = create_send_message_payload(text=user_queries[0])

    request = SendStreamingMessageRequest(params=MessageSendParams(**send_payload))

    print("--- Single Turn Streaming Request ---")
    stream_response = client.send_message_streaming(request)
    async for chunk in stream_response:
        print_json_response(chunk, "Streaming Chunk")


async def run_multi_turn_test(client: A2AClient) -> None:
    """Runs a multi-turn non-streaming test."""
    print("--- Multi-Turn Request ---")
    # --- First Turn ---

    first_turn_payload = create_send_message_payload(text=[user_queries[1]])
    request1 = SendMessageRequest(params=MessageSendParams(**first_turn_payload))
    first_turn_response: SendMessageResponse = await client.send_message(request1)
    print_json_response(first_turn_response, "Multi-Turn: First Turn Response")

    context_id: str | None = None
    if isinstance(first_turn_response.root, SendMessageSuccessResponse) and isinstance(
        first_turn_response.root.result, Task
    ):
        task: Task = first_turn_response.root.result
        context_id = task.contextId  # Capture context ID

        # --- Second Turn (if input required) ---
        if task.status.state == TaskState.input_required and context_id:
            print("--- Multi-Turn: Second Turn (Input Required) ---")
            second_turn_payload = create_send_message_payload(
                "in GBP", task.id, context_id
            )
            request2 = SendMessageRequest(
                params=MessageSendParams(**second_turn_payload)
            )
            second_turn_response = await client.send_message(request2)
            print_json_response(
                second_turn_response, "Multi-Turn: Second Turn Response"
            )
        elif not context_id:
            print("Warning: Could not get context ID from first turn response.")
        else:
            print("First turn completed, no further input required for this test case.")


async def main() -> None:
    """Main function to run the tests."""
    print(f"Connecting to agent at {AGENT_URL}...")
    try:
        async with httpx.AsyncClient(timeout=120) as httpx_client:
            agent_card_client = A2ACardResolver(httpx_client=httpx_client,base_url=AGENT_URL)
            agent_card = await agent_card_client.get_agent_card()
            print(f"Agent card: {agent_card}")

            client = await A2AClient.get_client_from_agent_card_url(
                httpx_client, AGENT_URL
            )
            print("Connection successful.")


            
            await run_single_turn_test(client)
            # await run_streaming_test(client)
            # await run_multi_turn_test(client)

    except Exception as e:
        traceback.print_exc()
        print(f"An error occurred: {e}")
        print("Ensure the agent server is running.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
