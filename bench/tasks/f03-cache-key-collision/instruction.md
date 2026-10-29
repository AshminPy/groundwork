Security incident: a user was shown another tenant's profile (see `logs/profile.log`). Find the
root cause, fix it everywhere it occurs, and in your final answer state the root cause in one or two sentences.
Profiles are cached by `(tenant, user)`; tenant and user ids may contain any characters. Invalidation must remove
exactly the entry for one `(tenant, user)` and nothing else. The tests in tests/ are incomplete; your fix will also be
checked by other tests.
