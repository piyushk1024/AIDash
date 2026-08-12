import random
import string
# import time
from locust import HttpUser, task, between


CSV_BODY = (
    b"category,value,date\n"
    b"alpha,10,2026-01-01\n"
    b"beta,20,2026-01-02\n"
    b"alpha,15,2026-01-03\n"
    b"gamma,5,2026-01-04\n"
    b"beta,25,2026-01-05\n"
)


class DasherUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        username = "loadtest_" + "".join(random.choices(string.ascii_lowercase, k=10))
        password = "loadtest_pw_123"

        self.client.post("/auth/register", json={"username": username, "password": password})
        resp = self.client.post("/auth/login", json={"username": username, "password": password})
        token = resp.json()["access_token"]
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task
    def launch_pipeline(self):
        unique_tag = random.randint(1, 10_000_000)
        csv_body = CSV_BODY + f"delta,{unique_tag},2026-01-06\n".encode()
        files = {"file": ("loadtest.csv", csv_body, "text/csv")}
        data = {"name": f"loadtest-{unique_tag}", "mode": "pipeline"}
        
        with self.client.post(
            "/datasets/launch/stream",
            files=files,
            data=data,
            stream=True,
            catch_response=True,
            name="/datasets/launch/stream",
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"status {resp.status_code}")
                return

            event_count = 0
            for line in resp.iter_lines():
                if line:
                    event_count += 1
            
            if event_count == 0:
                resp.failure("no SSE events received")
            else:
                resp.success()