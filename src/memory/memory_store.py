"""记忆系统 - 记住每个人的信息、喜好、故事"""

import json
import os
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Fact(BaseModel):
    """一条关于某人的事实"""
    content: str
    category: str = "general"  # general, preference, birthday, hobby, story, important
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    importance: int = 5  # 1-10, 越高越重要


class PersonProfile(BaseModel):
    """一个人的完整画像"""
    name: str
    nickname: str = ""
    relationship_type: str = "朋友"  # 朋友/暧昧/恋人/前任/同事/家人
    birthday: str = ""
    first_met: str = ""
    notes: str = ""
    facts: list[Fact] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class MemoryStore:
    """持久化记忆存储"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.people_file = os.path.join(data_dir, "people.json")
        self.global_file = os.path.join(data_dir, "global_memory.json")
        os.makedirs(data_dir, exist_ok=True)
        self._people: dict[str, PersonProfile] = {}
        self._global_facts: list[Fact] = []
        self._load()

    def _load(self):
        if os.path.exists(self.people_file):
            with open(self.people_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for name, pdata in data.items():
                    self._people[name] = PersonProfile(**pdata)
        if os.path.exists(self.global_file):
            with open(self.global_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._global_facts = [Fact(**fact) for fact in data.get("facts", [])]

    def _save(self):
        with open(self.people_file, "w", encoding="utf-8") as f:
            json.dump({name: p.model_dump() for name, p in self._people.items()},
                      f, ensure_ascii=False, indent=2)
        with open(self.global_file, "w", encoding="utf-8") as f:
            json.dump({"facts": [fact.model_dump() for fact in self._global_facts]},
                      f, ensure_ascii=False, indent=2)

    # ---- 人物管理 ----

    def add_person(self, name: str, **kwargs) -> PersonProfile:
        if name in self._people:
            return self._people[name]
        profile = PersonProfile(name=name, **kwargs)
        self._people[name] = profile
        self._save()
        return profile

    def get_person(self, name: str) -> Optional[PersonProfile]:
        return self._people.get(name)

    def list_people(self) -> list[PersonProfile]:
        return list(self._people.values())

    def update_person(self, name: str, **kwargs) -> Optional[PersonProfile]:
        profile = self._people.get(name)
        if not profile:
            return None
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        profile.updated_at = datetime.now().isoformat()
        self._save()
        return profile

    def delete_person(self, name: str) -> bool:
        if name in self._people:
            del self._people[name]
            self._save()
            return True
        return False

    # ---- 事实记忆 ----

    def remember(self, person_name: str, content: str,
                 category: str = "general", importance: int = 5) -> Fact:
        profile = self._people.get(person_name)
        if not profile:
            profile = self.add_person(person_name)
        fact = Fact(content=content, category=category, importance=importance)
        profile.facts.append(fact)
        profile.updated_at = datetime.now().isoformat()
        self._save()
        return fact

    def recall(self, person_name: str, limit: int = 20) -> list[Fact]:
        profile = self._people.get(person_name)
        if not profile:
            return []
        sorted_facts = sorted(profile.facts, key=lambda f: f.importance, reverse=True)
        return sorted_facts[:limit]

    def remember_global(self, content: str, category: str = "general",
                        importance: int = 5) -> Fact:
        fact = Fact(content=content, category=category, importance=importance)
        self._global_facts.append(fact)
        self._save()
        return fact

    def search(self, keyword: str) -> list[tuple[str, Fact]]:
        """搜索所有记忆中包含关键词的事实"""
        results = []
        for name, profile in self._people.items():
            for fact in profile.facts:
                if keyword.lower() in fact.content.lower():
                    results.append((name, fact))
        return results

    # ---- 统计 ----

    def stats(self) -> dict:
        return {
            "total_people": len(self._people),
            "total_facts": sum(len(p.facts) for p in self._people.values()),
            "global_facts": len(self._global_facts),
            "by_type": self._count_by_type(),
        }

    def _count_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for p in self._people.values():
            counts[p.relationship_type] = counts.get(p.relationship_type, 0) + 1
        return counts
