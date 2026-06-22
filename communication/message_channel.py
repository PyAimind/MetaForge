import queue
import config
from communication.message import Message

class MessageChannel:
    def __init__(self):
        self._queues = {name: queue.Queue() for name in config.AGENT_NAMES}

    def send(self, message: Message) -> None:
        if message.receiver not in self._queues:
            raise ValueError("Unknown receiver: " + message.receiver)
        self._queues[message.receiver].put(message)

    def receive(self, agent_name: str, timeout: float = None) -> Message:
        if agent_name not in self._queues:
            raise ValueError("Unknown agent: " + agent_name)
        return self._queues[agent_name].get(timeout=timeout)

    def has_messages(self, agent_name: str) -> bool:
        if agent_name not in self._queues:
            raise ValueError("Unknown agent: " + agent_name)
        return not self._queues[agent_name].empty()

    def queue_size(self, agent_name: str) -> int:
        if agent_name not in self._queues:
            raise ValueError("Unknown agent: " + agent_name)
        return self._queues[agent_name].qsize()