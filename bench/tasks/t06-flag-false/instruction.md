Setting `NEW_CHECKOUT=false` in the environment still turns the new checkout on (see
`logs/flags.log`). Find the root cause, fix it in the code, and in your final answer state the root cause in one or two sentences. The tests in tests/ are incomplete; your fix will also be checked by other tests. Accept `1, true, yes, on` and `0, false, no, off` in any letter case, with surrounding
spaces ignored; an unset or empty variable uses the default; anything else raises `ValueError`.
