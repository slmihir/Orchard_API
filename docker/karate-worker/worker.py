#!/usr/bin/env python3
"""
Karate Worker - Executes Karate tests and reports results via Redis.

This worker:
1. Polls Redis queue for Karate jobs
2. Writes .feature files to temporary directory
3. Executes Karate via subprocess
4. Parses Cucumber JSON report
5. Publishes results back to Redis
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import glob
from datetime import datetime
from pathlib import Path

import redis

# Configuration from environment
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
POLL_TIMEOUT = int(os.environ.get("POLL_TIMEOUT", "30"))  # Seconds to wait for jobs
JOB_TIMEOUT = int(os.environ.get("JOB_TIMEOUT", "300"))  # Max seconds per job
KARATE_JAR = os.environ.get("KARATE_JAR", "/opt/karate.jar")

# Redis keys
JOB_QUEUE = "karate:jobs"
STATUS_PREFIX = "karate:status:"
RESULT_PREFIX = "karate:results:"

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("karate-worker")


def connect_redis() -> redis.Redis:
    """Create Redis connection with retry."""
    max_retries = 5
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            client = redis.from_url(REDIS_URL, decode_responses=True)
            client.ping()
            logger.info(f"Connected to Redis at {REDIS_URL}")
            return client
        except redis.ConnectionError as e:
            logger.warning(f"Redis connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2

    logger.error("Failed to connect to Redis after all retries")
    sys.exit(1)


def process_job(job: dict, workspace_dir: str) -> dict:
    """
    Execute a Karate job and return results.

    Args:
        job: Job configuration from Redis queue
        workspace_dir: Temporary directory for test files

    Returns:
        Result dictionary with status, report, and timing
    """
    job_id = job.get("id", "unknown")
    started_at = datetime.utcnow()

    logger.info(f"Processing job {job_id}")

    try:
        # Write .feature file
        feature_content = job.get("feature", "")
        feature_path = os.path.join(workspace_dir, "test.feature")

        with open(feature_path, "w") as f:
            f.write(feature_content)
        logger.debug(f"Wrote feature file: {feature_path}")

        # #region agent log
        try:
            import urllib.request

            log_data = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "A",
                "location": "worker.py:90",
                "message": "Feature file written",
                "data": {
                    "job_id": job_id,
                    "feature_path": feature_path,
                    "feature_length": len(feature_content),
                    "feature_content": feature_content[:1000],
                },
                "timestamp": int(time.time() * 1000),
            }
            req = urllib.request.Request(
                "http://127.0.0.1:7242/ingest/ffd5fa03-dbab-4fa7-aaaf-9a9dfba56c80",
                data=json.dumps(log_data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=0.5)
        except Exception:
            pass
        # #endregion

        # Write karate-config.js if provided
        config_content = job.get("config")
        if config_content:
            config_path = os.path.join(workspace_dir, "karate-config.js")
            with open(config_path, "w") as f:
                f.write(config_content)
            logger.debug(f"Wrote config file: {config_path}")

        # Write additional files if provided
        additional_files = job.get("additional_files", {})
        for filename, content in additional_files.items():
            file_path = os.path.join(workspace_dir, filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f:
                f.write(content)
            logger.debug(f"Wrote additional file: {file_path}")

        # Build environment with job env vars
        env = os.environ.copy()
        env_vars = job.get("env_vars", {})
        for key, value in env_vars.items():
            env[key] = str(value)

        # Build Karate command
        # Note: we explicitly request Cucumber JSON output so the backend
        # can parse unified results. Without -f cucumber:json, Karate 1.4.x
        # will only emit HTML reports and our worker would treat the run as
        # "error" even if HTTP calls passed.
        cmd = [
            "java",
            "-jar", KARATE_JAR,
            feature_path,
            "-o", workspace_dir,
            "-f", "cucumber:json",
        ]

        # Add tags if provided
        tags = job.get("tags", [])
        if tags:
            cmd.extend(["-t", ",".join(tags)])

        logger.info(f"Executing: {' '.join(cmd)}")

        # Execute Karate
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            timeout=JOB_TIMEOUT,
            cwd=workspace_dir,
        )

        finished_at = datetime.utcnow()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        # Log output for debugging
        stdout_text = result.stdout.decode() if result.stdout else ""
        stderr_text = result.stderr.decode() if result.stderr else ""
        if result.stdout:
            logger.debug(f"Karate stdout: {stdout_text[:1000]}")
        if result.stderr:
            logger.debug(f"Karate stderr: {stderr_text[:1000]}")

        # #region agent log
        try:
            import urllib.request

            log_data = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "B,D",
                "location": "worker.py:138",
                "message": "Karate execution completed",
                "data": {
                    "job_id": job_id,
                    "returncode": result.returncode,
                    "stdout_preview": stdout_text[:500],
                    "stderr_preview": stderr_text[:500],
                    "duration_ms": duration_ms,
                },
                "timestamp": int(time.time() * 1000),
            }
            req = urllib.request.Request(
                "http://127.0.0.1:7242/ingest/ffd5fa03-dbab-4fa7-aaaf-9a9dfba56c80",
                data=json.dumps(log_data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=0.5)
        except Exception:
            pass
        # #endregion

        # Find and read Cucumber JSON report
        # Karate generates reports in target/karate-reports/ or workspace/karate-reports/
        report_patterns = [
            os.path.join(workspace_dir, "target", "karate-reports", "*.json"),
            os.path.join(workspace_dir, "karate-reports", "*.json"),
            os.path.join(workspace_dir, "*.json"),
        ]

        cucumber_report = None
        http_captures = None
        found_files = []
        for pattern in report_patterns:
            json_files = glob.glob(pattern)
            found_files.extend(json_files)
            for json_file in json_files:
                # Skip summary files, look for the actual report
                if "karate-summary" in json_file:
                    continue

                # Check for http-captures.json file
                if "http-captures" in json_file:
                    try:
                        with open(json_file, "r") as f:
                            http_captures = json.loads(f.read())
                            logger.info(f"Found HTTP captures: {json_file}")
                    except (json.JSONDecodeError, IOError) as e:
                        logger.debug(f"Could not read HTTP captures {json_file}: {e}")
                    continue

                try:
                    with open(json_file, "r") as f:
                        content = f.read()
                        # Cucumber reports start with [
                        if content.strip().startswith("["):
                            cucumber_report = json.loads(content)
                            logger.info(f"Found Cucumber report: {json_file}")
                            break
                except (json.JSONDecodeError, IOError) as e:
                    logger.debug(f"Could not read {json_file}: {e}")

            if cucumber_report:
                break

        # Also search for http-captures.json in common locations if not found yet
        if http_captures is None:
            http_capture_paths = [
                os.path.join(workspace_dir, "http-captures.json"),
                os.path.join(workspace_dir, "target", "http-captures.json"),
                os.path.join(workspace_dir, "target", "karate-reports", "http-captures.json"),
            ]
            for capture_path in http_capture_paths:
                if os.path.exists(capture_path):
                    try:
                        with open(capture_path, "r") as f:
                            http_captures = json.loads(f.read())
                            logger.info(f"Found HTTP captures: {capture_path}")
                            break
                    except (json.JSONDecodeError, IOError) as e:
                        logger.debug(f"Could not read HTTP captures {capture_path}: {e}")

        # #region agent log
        try:
            import urllib.request

            log_data = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "C",
                "location": "worker.py:177",
                "message": "Report search completed",
                "data": {
                    "job_id": job_id,
                    "found_files": found_files,
                    "found_files_count": len(found_files),
                    "cucumber_report_found": cucumber_report is not None,
                    "workspace_dir": workspace_dir,
                },
                "timestamp": int(time.time() * 1000),
            }
            req = urllib.request.Request(
                "http://127.0.0.1:7242/ingest/ffd5fa03-dbab-4fa7-aaaf-9a9dfba56c80",
                data=json.dumps(log_data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=0.5)
        except Exception:
            pass
        # #endregion

        # Determine status
        if result.returncode == 0 and cucumber_report:
            status = "complete"
        elif cucumber_report:
            # Tests ran but had failures
            status = "complete"
        else:
            status = "error"

        return {
            "job_id": job_id,
            "status": status,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_ms": duration_ms,
            "report": cucumber_report,
            "http_captures": http_captures,
            "exit_code": result.returncode,
            "error": result.stderr.decode()[:2000] if result.returncode != 0 and not cucumber_report else None,
        }

    except subprocess.TimeoutExpired:
        finished_at = datetime.utcnow()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        logger.error(f"Job {job_id} timed out after {JOB_TIMEOUT} seconds")
        return {
            "job_id": job_id,
            "status": "error",
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_ms": duration_ms,
            "error": f"Timeout: Job exceeded {JOB_TIMEOUT} seconds",
        }

    except Exception as e:
        finished_at = datetime.utcnow()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        logger.exception(f"Job {job_id} failed with exception")
        return {
            "job_id": job_id,
            "status": "error",
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_ms": duration_ms,
            "error": str(e),
        }


def main():
    """Main worker loop."""
    logger.info("Karate Worker starting...")
    logger.info(f"Karate JAR: {KARATE_JAR}")
    logger.info(f"Redis URL: {REDIS_URL}")
    logger.info(f"Poll timeout: {POLL_TIMEOUT}s, Job timeout: {JOB_TIMEOUT}s")

    # Verify Karate JAR exists
    if not os.path.exists(KARATE_JAR):
        logger.error(f"Karate JAR not found at {KARATE_JAR}")
        sys.exit(1)

    # Connect to Redis
    redis_client = connect_redis()

    logger.info("Worker ready, waiting for jobs...")

    while True:
        try:
            # Blocking pop from queue with timeout
            result = redis_client.brpop(JOB_QUEUE, timeout=POLL_TIMEOUT)

            if result is None:
                # Timeout, no jobs available
                continue

            _, job_json = result
            job = json.loads(job_json)
            job_id = job.get("id", "unknown")

            # Check if job was cancelled
            status = redis_client.get(f"{STATUS_PREFIX}{job_id}")
            if status == "cancelled":
                logger.info(f"Job {job_id} was cancelled, skipping")
                continue

            # Update status to running
            redis_client.set(f"{STATUS_PREFIX}{job_id}", "running", ex=3600)

            # Create temporary workspace
            with tempfile.TemporaryDirectory(prefix="karate_") as workspace:
                logger.debug(f"Created workspace: {workspace}")

                # Process the job
                result = process_job(job, workspace)

                # Publish result
                result_key = f"{RESULT_PREFIX}{job_id}"
                redis_client.set(result_key, json.dumps(result), ex=3600)

                # Update status
                final_status = "complete" if result.get("status") == "complete" else "error"
                redis_client.set(f"{STATUS_PREFIX}{job_id}", final_status, ex=3600)

                logger.info(f"Job {job_id} completed with status: {final_status}")

        except redis.ConnectionError as e:
            logger.error(f"Redis connection error: {e}")
            logger.info("Attempting to reconnect...")
            time.sleep(5)
            redis_client = connect_redis()

        except KeyboardInterrupt:
            logger.info("Shutting down worker...")
            break

        except Exception as e:
            logger.exception(f"Unexpected error in worker loop: {e}")
            time.sleep(5)  # Prevent tight error loop

    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
