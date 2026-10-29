`max_retries=3` is configured, which should mean 1 attempt plus up to 3 retries, but the logs show
a failing upload giving up after 3 attempts in total (see `logs/upload.log`). Find the root cause, fix it in the code, and in your final answer state the root cause in one or two sentences. The tests in tests/ are incomplete; your fix will also be checked by other tests.
