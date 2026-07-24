import os
import json
import time

class KnowledgeBase:
    ROLE_TAGS = {
        "engineer": ["design", "architecture"],
        "coder": ["code", "import", "dependency"]
    }

    def __init__(self, storage_path: str = "memory/knowledge_base.json"):
        self.storage_path = storage_path
        directory = os.path.dirname(storage_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        try:
            with open(storage_path, 'r') as f:
                self.data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.data = {"lessons": [], "successes": [], "failures": []}

    def _generate_hash(self, title: str, tags: list) -> int:
        return hash(title + "".join(sorted(tags)))

    def _save(self) -> None:
        with open(self.storage_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def _add_entry(self, category: str, title: str, text_key: str, text_value: str, tags: list[str]) -> bool:
        if tags is None:
            tags = []
        h = self._generate_hash(title, tags)
        for entry in self.data[category]:
            if entry.get("hash") == h:
                return False
        entry = {
            "title": title,
            text_key: text_value,
            "tags": tags,
            "timestamp": time.time(),
            "hash": h
        }
        self.data[category].append(entry)
        self._save()
        return True

    def add_lesson(self, title: str, description: str, tags: list[str] = None) -> bool:
        return self._add_entry("lessons", title, "description", description, tags)

    def add_success(self, title: str, pattern: str, tags: list[str] = None) -> bool:
        return self._add_entry("successes", title, "pattern", pattern, tags)

    def add_failure(self, title: str, reason: str, tags: list[str] = None) -> bool:
        return self._add_entry("failures", title, "reason", reason, tags)

    def search(self, query: str = None, tags: list[str] = None, match: str = "any") -> dict:
        if tags is None:
            tags = []
        query = query.lower() if query else ""
        results = {"lessons": [], "successes": [], "failures": []}

        def entry_matches(entry, text_fields):
            has_query = bool(query)
            has_tags = bool(tags)
            text_match = any(query in entry.get(field, '').lower() for field in text_fields) if has_query else False
            tag_match = False
            if has_tags:
                entry_tags = set(entry.get("tags", []))
                if match == "any":
                    tag_match = any(t in entry_tags for t in tags)
                else:
                    tag_match = all(t in entry_tags for t in tags)
            if has_query and has_tags:
                if match == "any":
                    return text_match or tag_match
                else:
                    return text_match and tag_match
            elif has_query:
                return text_match
            elif has_tags:
                return tag_match
            else:
                return False

        for lesson in self.data["lessons"]:
            if entry_matches(lesson, ["title", "description"]):
                results["lessons"].append(lesson)
        for success in self.data["successes"]:
            if entry_matches(success, ["title", "pattern"]):
                results["successes"].append(success)
        for failure in self.data["failures"]:
            if entry_matches(failure, ["title", "reason"]):
                results["failures"].append(failure)
        for cat in results:
            results[cat] = sorted(results[cat], key=lambda x: x["timestamp"], reverse=True)
        return results

    def get_prompt_context(self, query: str, role: str) -> str:
        if role not in self.ROLE_TAGS:
            return ""
        tags = self.ROLE_TAGS[role]
        results = self.search(query=query, tags=tags, match="any")
        lessons = results.get("lessons", [])
        successes = results.get("successes", [])
        if not lessons and not successes:
            return ""
        all_items = []
        for item in lessons:
            all_items.append(("lesson", item))
        for item in successes:
            all_items.append(("success", item))
        all_items.sort(key=lambda x: x[1]["timestamp"], reverse=True)
        selected = all_items[:5]
        lines = ["### Relevant Knowledge:"]
        for kind, entry in selected:
            title = entry.get("title", "Untitled")
            if kind == "lesson":
                desc = entry.get("description", "")
                lines.append(f"- [Lesson]: {title} - {desc}")
            else:
                pattern = entry.get("pattern", "")
                lines.append(f"- [Success]: {title} - {pattern}")
        full_text = "\n".join(lines)
        if len(full_text) > 1000:
            truncated = lines[0]
            for line in lines[1:]:
                if len(truncated) + 1 + len(line) > 1000:
                    break
                truncated += "\n" + line
            full_text = truncated
        return full_text