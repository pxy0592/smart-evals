"""Active database managers used by evaluation_db.py."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.database import DatabaseManager, get_db_manager

_JSON_TASK_FIELDS = ("metrics", "knowledge_base_ids", "knowledge_base_names_snapshot")
_JSON_REPORT_FIELDS = ("overall_scores", "detailed_scores", "evaluation_metadata", "knowledge_base_ids", "source_snapshot", "warning")


def _decode_fields(item: Dict[str, Any], fields) -> Dict[str, Any]:
    for field in fields:
        if field in item and isinstance(item[field], str):
            try:
                item[field] = json.loads(item[field])
            except json.JSONDecodeError:
                item[field] = [] if field.endswith("ids") or field in {"metrics", "detailed_scores"} else {}
    return item


class ConfigManager:
    def __init__(self): self.db = get_db_manager()

    @staticmethod
    def _mask(key: str) -> str:
        if not key: return ""
        return "*" * len(key) if len(key) <= 8 else key[:4] + "*" * (len(key) - 8) + key[-4:]

    def get_api_configs(self):
        rows = self.db.get_api_configs()
        for row in rows: row["api_key"] = self._mask(row.get("api_key", ""))
        return rows

    def create_api_config(self, data): return self.db.create_api_config(data)
    def update_api_config(self, config_id, data): return self.db.update_api_config(config_id, data)
    def delete_api_config(self, config_id): return self.db.delete_api_config(config_id)

    def get_default_api_config(self):
        row = self.db.get_default_api_config()
        if not row: return None
        return {"id": row.get("id"), "name": row.get("name"), "provider": row.get("provider"), "apiKey": row.get("api_key"), "endpoint": row.get("endpoint"), "model": row.get("model"), "embeddingModel": row.get("embedding_model"), "temperature": row.get("temperature"), "maxTokens": row.get("max_tokens"), "isDefault": row.get("is_default")}

    def get_settings(self, category=None):
        conn = self.db.get_connection(); sql = "SELECT * FROM system_settings"; params=[]
        if category: sql += " WHERE category=?"; params.append(category)
        rows=[dict(r) for r in conn.execute(sql+" ORDER BY category,key",params)]; conn.close(); return rows

    def get_setting(self, key, default=None): return self.db.get_setting(key, default)
    def update_setting(self, key, value, description=None, category="general"): return self.db.update_setting(key, str(value), description, category)
    def update_settings_batch(self, settings):
        for key, value in settings.items(): self.update_setting(key, value)


class DatasetManager:
    def __init__(self): self.db = get_db_manager()
    def create_dataset(self, data): return self.db.create_dataset(data)
    def get_datasets(self, limit=20, offset=0): return self.db.get_datasets(limit, offset)
    def get_dataset(self, dataset_id): return self.db.get_dataset(dataset_id)

    def get_dataset_samples(self, dataset_id, offset=0, limit=None):
        dataset = self.get_dataset(dataset_id)
        if not dataset: raise FileNotFoundError(f"Dataset not found: {dataset_id}")
        path = dataset.get("normalized_storage_path") or os.path.join(os.getenv("DATASETS_DIR", "tmp/datasets"), f"{dataset_id}.json")
        if not os.path.exists(path): raise FileNotFoundError(f"Dataset samples not found: {path}")
        samples = json.loads(Path(path).read_text(encoding="utf-8"))
        return samples[offset : offset + limit] if limit is not None else samples[offset:]

    def update_dataset_status(self, dataset_id, status, **values): return self.db.update_dataset_status(dataset_id, status, **values)

    def delete_dataset(self, dataset_id):
        dataset = self.get_dataset(dataset_id)
        conn=self.db.get_connection(); cursor=conn.execute("DELETE FROM datasets WHERE id=?",(dataset_id,)); conn.commit(); conn.close()
        if dataset:
            for path in {dataset.get("storage_path"), dataset.get("normalized_storage_path")}:
                if path and os.path.isfile(path): os.remove(path)
        return cursor.rowcount > 0

    def get_dataset_statistics(self):
        conn=self.db.get_connection(); row=conn.execute("SELECT COUNT(*) total, SUM(has_reference) refs, SUM(has_contexts) ctx FROM datasets").fetchone(); conn.close()
        return {"total_count": row["total"] or 0, "with_reference_count": row["refs"] or 0, "with_contexts_count": row["ctx"] or 0, "recent_count": row["total"] or 0}


class TaskManager:
    def __init__(self): self.db=get_db_manager()
    def create_task(self,data): return self.db.create_evaluation_task(data)

    def get_tasks(self, limit=20, offset=0, status=None, rag_provider=None, rag_connection_id=None):
        where=[]; params=[]
        for field,value in (("status",status),("rag_provider",rag_provider),("rag_connection_id",rag_connection_id)):
            if value is not None: where.append(f"{field}=?"); params.append(value)
        clause=" WHERE "+" AND ".join(where) if where else ""
        conn=self.db.get_connection(); total=conn.execute("SELECT COUNT(*) FROM evaluation_tasks"+clause,params).fetchone()[0]
        rows=[_decode_fields(dict(r),_JSON_TASK_FIELDS) for r in conn.execute("SELECT * FROM evaluation_tasks"+clause+" ORDER BY created_at DESC LIMIT ? OFFSET ?",params+[limit,offset])]; conn.close()
        return {"tasks":rows,"total":total,"limit":limit,"offset":offset}

    def get_task(self, task_id):
        conn=self.db.get_connection(); row=conn.execute("SELECT * FROM evaluation_tasks WHERE id=?",(task_id,)).fetchone(); conn.close(); return _decode_fields(dict(row),_JSON_TASK_FIELDS) if row else None
    def update_task_status(self,task_id,status,**kwargs): return self.db.update_task_status(task_id,status,**kwargs)

    def delete_task(self,task_id):
        conn=self.db.get_connection(); cursor=conn.execute("DELETE FROM evaluation_tasks WHERE id=?",(task_id,)); conn.commit(); changed=cursor.rowcount>0; conn.close(); return changed

    def get_task_statistics(self):
        conn=self.db.get_connection(); rows=conn.execute("SELECT status,COUNT(*) count FROM evaluation_tasks GROUP BY status").fetchall(); counts={r["status"]:r["count"] for r in rows}; total=sum(counts.values())
        avg=conn.execute("SELECT AVG((julianday(completed_at)-julianday(created_at))*1440) FROM evaluation_tasks WHERE status='completed'").fetchone()[0] or 0; conn.close()
        return {"total_count":total,"status_counts":counts,"total_completed":counts.get("completed",0),"running_count":counts.get("running",0),"failed_count":counts.get("failed",0),"pending_count":counts.get("pending",0),"recent_count":total,"avg_processing_time":round(avg,1)}


class ReportManager:
    def __init__(self): self.db=get_db_manager()
    def save_report(self,data): return self.db.save_evaluation_report(data)
    def get_report(self,task_id): return self.db.get_evaluation_report(task_id)

    def get_reports(self, limit=20, offset=0, rag_provider=None, rag_connection_id=None, assistant_id=None, knowledge_base_id=None, start_date=None, end_date=None):
        where=[]; params=[]
        for field,value in (("rag_provider",rag_provider),("rag_connection_id",rag_connection_id),("assistant_id",assistant_id)):
            if value: where.append(f"{field}=?"); params.append(value)
        if knowledge_base_id: where.append("knowledge_base_ids LIKE ?"); params.append(f'%"{knowledge_base_id}"%')
        if start_date: where.append("date(created_at)>=date(?)"); params.append(start_date)
        if end_date: where.append("date(created_at)<=date(?)"); params.append(end_date)
        clause=" WHERE "+" AND ".join(where) if where else ""
        conn=self.db.get_connection(); total=conn.execute("SELECT COUNT(*) FROM evaluation_reports"+clause,params).fetchone()[0]; rows=[_decode_fields(dict(r),_JSON_REPORT_FIELDS) for r in conn.execute("SELECT * FROM evaluation_reports"+clause+" ORDER BY created_at DESC LIMIT ? OFFSET ?",params+[limit,offset])]; conn.close()
        return {"reports":rows,"total":total,"limit":limit,"offset":offset}

    def delete_report(self,task_id):
        conn=self.db.get_connection(); cursor=conn.execute("DELETE FROM evaluation_reports WHERE task_id=?",(task_id,)); conn.commit(); changed=cursor.rowcount>0; conn.close(); return changed
    def delete_reports_batch(self,task_ids):
        if not task_ids:return 0
        conn=self.db.get_connection(); placeholders=",".join("?" for _ in task_ids); cursor=conn.execute(f"DELETE FROM evaluation_reports WHERE task_id IN ({placeholders})",task_ids); conn.commit(); n=cursor.rowcount; conn.close(); return n

    def get_report_statistics(self):
        conn=self.db.get_connection(); rows=conn.execute("SELECT overall_scores FROM evaluation_reports ORDER BY created_at DESC LIMIT 20").fetchall(); conn.close(); metrics={}
        for row in rows:
            try: scores=json.loads(row["overall_scores"] or "{}")
            except json.JSONDecodeError: continue
            for name,data in scores.items():
                value=data.get("mean") if isinstance(data,dict) else data
                if isinstance(value,(int,float)): metrics.setdefault(name,[]).append(value)
        display={"answer_correctness":"答案正确性","faithfulness":"忠实度","context_precision":"上下文精准度","context_recall":"上下文召回率","answer_relevancy":"答案相关性"}
        averages=[{"name":display.get(k,k),"score":round(sum(v)/len(v)*100,1),"trend":"stable"} for k,v in metrics.items() if v]
        return {"recent_scores":[],"metric_averages":averages,"recent_count":len(rows)}


config_manager=None; dataset_manager=None; task_manager=None; report_manager=None

def get_config_manager():
    global config_manager
    if config_manager is None: config_manager=ConfigManager()
    return config_manager

def get_dataset_manager():
    global dataset_manager
    if dataset_manager is None: dataset_manager=DatasetManager()
    return dataset_manager

def get_task_manager():
    global task_manager
    if task_manager is None: task_manager=TaskManager()
    return task_manager

def get_report_manager():
    global report_manager
    if report_manager is None: report_manager=ReportManager()
    return report_manager
