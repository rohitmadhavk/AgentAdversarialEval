========================================================
  prompt_a_verbose  [cases 1–4 CRUD block]
========================================================
  [01/4] Case 01 [H] Add 'buy groceries' to my task list.…
    ✓ called=manage_tasks expected=manage_tasks  (0.50s net)
  [02/4] Case 02 [H] Show me all my current tasks.…
    ✓ called=manage_tasks expected=manage_tasks  (0.36s net)
  [03/4] Case 03 [H] Mark task number 1 as complete.…
    ✓ called=manage_tasks expected=manage_tasks  (0.39s net)
  [04/4] Case 04 [H] Delete the first task in my list.…
    ✓ called=manage_tasks expected=manage_tasks  (1.38s net)

========================================================
  prompt_b_terse  [cases 1–4 CRUD block]
========================================================
  [01/4] Case 01 [H] Add 'buy groceries' to my task list.…
    ✓ called=manage_tasks expected=manage_tasks  (0.43s net)
  [02/4] Case 02 [H] Show me all my current tasks.…
    ✓ called=manage_tasks expected=manage_tasks  (0.40s net)
  [03/4] Case 03 [H] Mark task number 1 as complete.…
    ✓ called=manage_tasks expected=manage_tasks  (0.35s net)
  [04/4] Case 04 [H] Delete the first task in my list.…
    ✗ called=none expected=manage_tasks  (0.87s net)

========================================================
  prompt_c_positive  [cases 1–4 CRUD block]
========================================================
  [01/4] Case 01 [H] Add 'buy groceries' to my task list.…
    ✓ called=manage_tasks expected=manage_tasks  (0.33s net)
  [02/4] Case 02 [H] Show me all my current tasks.…
    ✓ called=manage_tasks expected=manage_tasks  (0.47s net)
  [03/4] Case 03 [H] Mark task number 1 as complete.…
    ✓ called=manage_tasks expected=manage_tasks  (0.36s net)
  [04/4] Case 04 [H] Delete the first task in my list.…
    ✓ called=manage_tasks expected=manage_tasks  (0.87s net)

========================================================
  prompt_a_verbose | case 9
========================================================
  [01/48] Case 09 [H] Is it cold in Chicago today?…
    ✓ called=get_weather expected=get_weather  (1.23s net)

========================================================
  prompt_b_terse | case 9
========================================================
  [02/48] Case 09 [H] Is it cold in Chicago today?…
    ✓ called=get_weather expected=get_weather  (0.62s net)

========================================================
  prompt_c_positive | case 9
========================================================
  [03/48] Case 09 [H] Is it cold in Chicago today?…
    ✓ called=get_weather expected=get_weather  (0.77s net)

========================================================
  prompt_a_verbose | case 20
========================================================
  [04/48] Case 20 [O] What's the weather like in Cairo right now?…
    ✓ abstained ✓  (0.19s net)

========================================================
  prompt_b_terse | case 20
========================================================
  [05/48] Case 20 [O] What's the weather like in Cairo right now?…
    ✓ abstained ✓  (0.21s net)

========================================================
  prompt_c_positive | case 20
========================================================
  [06/48] Case 20 [O] What's the weather like in Cairo right now?…
    ✓ abstained ✓  (0.19s net)

========================================================
  prompt_a_verbose | case 6
========================================================
  [07/48] Case 06 [H] How many pounds is 75 kilograms?…
    ✓ called=convert_units expected=convert_units  (0.83s net)

========================================================
  prompt_b_terse | case 6
========================================================
  [08/48] Case 06 [H] How many pounds is 75 kilograms?…
    ✓ called=convert_units expected=convert_units  (0.48s net)

========================================================
  prompt_c_positive | case 6
========================================================
  [09/48] Case 06 [H] How many pounds is 75 kilograms?…
    ✓ called=convert_units expected=convert_units  (0.40s net)

========================================================
  prompt_a_verbose | case 17
========================================================
  [10/48] Case 17 [O] What is the capital of Australia?…
    ✓ abstained ✓  (0.30s net)

========================================================
  prompt_b_terse | case 17
========================================================
  [11/48] Case 17 [O] What is the capital of Australia?…
    ✓ abstained ✓  (0.21s net)

========================================================
  prompt_c_positive | case 17
========================================================
  [12/48] Case 17 [O] What is the capital of Australia?…
    ✓ abstained ✓  (0.33s net)

========================================================
  prompt_a_verbose | case 18
========================================================
  [13/48] Case 18 [O] What was the weather like in Chicago last Tuesday?…
    ✓ abstained ✓  (0.41s net)

========================================================
  prompt_b_terse | case 18
========================================================
  [14/48] Case 18 [O] What was the weather like in Chicago last Tuesday?…
    ✓ abstained ✓  (0.21s net)

========================================================
  prompt_c_positive | case 18
========================================================
  [15/48] Case 18 [O] What was the weather like in Chicago last Tuesday?…
    ✓ abstained ✓  (0.29s net)

========================================================
  prompt_a_verbose | case 5
========================================================
  [16/48] Case 05 [H] Convert 100 kilometers to miles.…
    ✓ called=convert_units expected=convert_units  (0.33s net)

========================================================
  prompt_b_terse | case 5
========================================================
  [17/48] Case 05 [H] Convert 100 kilometers to miles.…
    ✓ called=convert_units expected=convert_units  (0.74s net)

========================================================
  prompt_c_positive | case 5
========================================================
  [18/48] Case 05 [H] Convert 100 kilometers to miles.…
    ✓ called=convert_units expected=convert_units  (0.34s net)

========================================================
  prompt_a_verbose | case 14
========================================================
  [19/48] Case 14 [A] Add a task to check if it's going to rain in Houston…
    ✓ called=manage_tasks preferred=manage_tasks — 'Add a task' is an explicit store-a-reminder instruction.  (0.47s net)

========================================================
  prompt_b_terse | case 14
========================================================
  [20/48] Case 14 [A] Add a task to check if it's going to rain in Houston…
    ✓ called=manage_tasks preferred=manage_tasks — 'Add a task' is an explicit store-a-reminder instruction.  (0.59s net)

========================================================
  prompt_c_positive | case 14
========================================================
  [21/48] Case 14 [A] Add a task to check if it's going to rain in Houston…
    ✓ called=manage_tasks preferred=manage_tasks — 'Add a task' is an explicit store-a-reminder instruction.  (0.83s net)

========================================================
  prompt_a_verbose | case 16
========================================================
  [22/48] Case 16 [O] Write me a poem about autumn leaves.…
    ✓ abstained ✓  (1.36s net)

========================================================
  prompt_b_terse | case 16
========================================================
  [23/48] Case 16 [O] Write me a poem about autumn leaves.…
    ✓ abstained ✓  (0.30s net)

========================================================
  prompt_c_positive | case 16
========================================================
  [24/48] Case 16 [O] Write me a poem about autumn leaves.…
    ✓ abstained ✓  (0.26s net)

========================================================
  prompt_a_verbose | case 7
========================================================
  [25/48] Case 07 [H] What is 32 degrees Fahrenheit in Celsius?…
    ✓ called=convert_units expected=convert_units  (0.45s net)

========================================================
  prompt_b_terse | case 7
========================================================
  [26/48] Case 07 [H] What is 32 degrees Fahrenheit in Celsius?…
    ✓ called=convert_units expected=convert_units  (0.89s net)

========================================================
  prompt_c_positive | case 7
========================================================
  [27/48] Case 07 [H] What is 32 degrees Fahrenheit in Celsius?…
    ✓ called=convert_units expected=convert_units  (0.40s net)

========================================================
  prompt_a_verbose | case 8
========================================================
  [28/48] Case 08 [H] What's the weather like in New York right now?…
    ✓ called=get_weather expected=get_weather  (0.99s net)

========================================================
  prompt_b_terse | case 8
========================================================
  [29/48] Case 08 [H] What's the weather like in New York right now?…
    ✓ called=get_weather expected=get_weather  (0.76s net)

========================================================
  prompt_c_positive | case 8
========================================================
  [30/48] Case 08 [H] What's the weather like in New York right now?…
    ✓ called=get_weather expected=get_weather  (1.22s net)

========================================================
  prompt_a_verbose | case 12
========================================================
  [31/48] Case 12 [A] I need to remember to check the weather in Seattle b…
    ✓ called=manage_tasks preferred=manage_tasks — Explicit reminder intent — user wants a to-do entry, not a forecast.  (0.58s net)

========================================================
  prompt_b_terse | case 12
========================================================
  [32/48] Case 12 [A] I need to remember to check the weather in Seattle b…
    ✓ called=manage_tasks preferred=manage_tasks — Explicit reminder intent — user wants a to-do entry, not a forecast.  (0.51s net)

========================================================
  prompt_c_positive | case 12
========================================================
  [33/48] Case 12 [A] I need to remember to check the weather in Seattle b…
    ✓ called=manage_tasks preferred=manage_tasks — Explicit reminder intent — user wants a to-do entry, not a forecast.  (0.49s net)

========================================================
  prompt_a_verbose | case 10
========================================================
  [34/48] Case 10 [H] What's the current temperature in Los Angeles?…
    ✓ called=get_weather expected=get_weather  (0.84s net)

========================================================
  prompt_b_terse | case 10
========================================================
  [35/48] Case 10 [H] What's the current temperature in Los Angeles?…
    ✓ called=get_weather expected=get_weather  (0.54s net)

========================================================
  prompt_c_positive | case 10
========================================================
  [36/48] Case 10 [H] What's the current temperature in Los Angeles?…
    ✓ called=get_weather expected=get_weather  (0.64s net)

========================================================
  prompt_a_verbose | case 11
========================================================
  [37/48] Case 11 [A] Should I bring a jacket to my meeting in Miami today…
    ✓ called=get_weather preferred=get_weather — Weather is the root question; the jacket is just context.  (1.02s net)

========================================================
  prompt_b_terse | case 11
========================================================
  [38/48] Case 11 [A] Should I bring a jacket to my meeting in Miami today…
    ✓ called=get_weather preferred=get_weather — Weather is the root question; the jacket is just context.  (0.83s net)

========================================================
  prompt_c_positive | case 11
========================================================
  [39/48] Case 11 [A] Should I bring a jacket to my meeting in Miami today…
    ✓ called=get_weather preferred=get_weather — Weather is the root question; the jacket is just context.  (0.78s net)

========================================================
  prompt_a_verbose | case 13
========================================================
  [40/48] Case 13 [A] Convert the temperature in Boston right now to Celsi…
    ✓ called=get_weather preferred=get_weather — No numeric value is in the conversation — get_weather must run first to fetch the current temperature; convert_units requires a known input value.  (1.35s net)

========================================================
  prompt_b_terse | case 13
========================================================
  [41/48] Case 13 [A] Convert the temperature in Boston right now to Celsi…
    ✓ called=get_weather preferred=get_weather — No numeric value is in the conversation — get_weather must run first to fetch the current temperature; convert_units requires a known input value.  (1.39s net)

========================================================
  prompt_c_positive | case 13
========================================================
  [42/48] Case 13 [A] Convert the temperature in Boston right now to Celsi…
    ✓ called=get_weather preferred=get_weather — No numeric value is in the conversation — get_weather must run first to fetch the current temperature; convert_units requires a known input value.  (1.44s net)

========================================================
  prompt_a_verbose | case 15
========================================================
  [43/48] Case 15 [A] The forecast says Seattle is 28 degrees Celsius toda…
    ✓ called=convert_units preferred=convert_units — The numeric value (28°C) is already in the prompt — convert_units can run immediately; fetching weather would be redundant since the temperature is already known.  (0.54s net)

========================================================
  prompt_b_terse | case 15
========================================================
  [44/48] Case 15 [A] The forecast says Seattle is 28 degrees Celsius toda…
    ✓ called=convert_units preferred=convert_units — The numeric value (28°C) is already in the prompt — convert_units can run immediately; fetching weather would be redundant since the temperature is already known.  (0.47s net)

========================================================
  prompt_c_positive | case 15
========================================================
  [45/48] Case 15 [A] The forecast says Seattle is 28 degrees Celsius toda…
    ✓ called=convert_units preferred=convert_units — The numeric value (28°C) is already in the prompt — convert_units can run immediately; fetching weather would be redundant since the temperature is already known.  (0.70s net)

========================================================
  prompt_a_verbose | case 19
========================================================
  [46/48] Case 19 [O] What's the current USD to EUR exchange rate?…
    ✓ abstained ✓  (0.16s net)

========================================================
  prompt_b_terse | case 19
========================================================
  [47/48] Case 19 [O] What's the current USD to EUR exchange rate?…
    ✓ abstained ✓  (0.16s net)

========================================================
  prompt_c_positive | case 19
========================================================
  [48/48] Case 19 [O] What's the current USD to EUR exchange rate?…
    ✓ abstained ✓  (0.22s net)

========================================================
  FAULT INJECTION  (prompt_a_verbose)
========================================================
  [01/3] Case 01 [FAULT/manage_tasks] Add 'buy groceries' to my task list.…
    ✓ tool=manage_tasks errored=True survived=True  (0.61s net)
  [02/3] Case 05 [FAULT/convert_units] Convert 100 kilometers to miles.…
    ✓ tool=convert_units errored=True survived=True  (0.60s net)
  [03/3] Case 08 [FAULT/get_weather] What's the weather like in New York right now?…
    ✓ tool=get_weather errored=True survived=True  (0.50s net)

========================================================
  FAULT INJECTION  (prompt_b_terse)
========================================================
  [01/3] Case 01 [FAULT/manage_tasks] Add 'buy groceries' to my task list.…
    ✓ tool=manage_tasks errored=True survived=True  (0.40s net)
  [02/3] Case 05 [FAULT/convert_units] Convert 100 kilometers to miles.…
    ✓ tool=convert_units errored=True survived=True  (0.70s net)
  [03/3] Case 08 [FAULT/get_weather] What's the weather like in New York right now?…
    ✓ tool=get_weather errored=True survived=True  (0.52s net)

========================================================
  FAULT INJECTION  (prompt_c_positive)
========================================================
  [01/3] Case 01 [FAULT/manage_tasks] Add 'buy groceries' to my task list.…
    ✓ tool=manage_tasks errored=True survived=True  (0.79s net)
  [02/3] Case 05 [FAULT/convert_units] Convert 100 kilometers to miles.…
    ✓ tool=convert_units errored=True survived=True  (0.49s net)
  [03/3] Case 08 [FAULT/get_weather] What's the weather like in New York right now?…
    ✓ tool=get_weather errored=True survived=True  (0.38s net)

========================================================
  RESULTS SUMMARY
========================================================

  ── prompt_a_verbose ──
    Tool accuracy  (happy-path):  100%  (10/10)
      convert_units         3/3
      get_weather           3/3
      manage_tasks          4/4
    Preferred tool (ambiguous):   100%  (5/5)
    Abstention rate (OOS):        100%  (5/5)
    p95 latency:                  1.36s
    mean latency:                 0.68s

  ── prompt_b_terse ──
    Tool accuracy  (happy-path):  90%  (9/10)
      convert_units         3/3
      get_weather           3/3
      manage_tasks          3/4
    Preferred tool (ambiguous):   100%  (5/5)
    Abstention rate (OOS):        100%  (5/5)
    p95 latency:                  0.89s
    mean latency:                 0.55s
    Failures (1):
      Case 04 [H]: called=none expected=manage_tasks

  ── prompt_c_positive ──
    Tool accuracy  (happy-path):  100%  (10/10)
      convert_units         3/3
      get_weather           3/3
      manage_tasks          4/4
    Preferred tool (ambiguous):   100%  (5/5)
    Abstention rate (OOS):        100%  (5/5)
    p95 latency:                  1.22s
    mean latency:                 0.57s

  ── Fault injection ──
    prompt_a_verbose  (3 case(s), tools: convert_units, get_weather, manage_tasks)
      Graceful degradation:       3/3
        Case 01 [manage_tasks]: tool=manage_tasks errored=True survived=True
        Case 05 [convert_units]: tool=convert_units errored=True survived=True
        Case 08 [get_weather]: tool=get_weather errored=True survived=True
    prompt_b_terse  (3 case(s), tools: convert_units, get_weather, manage_tasks)
      Graceful degradation:       3/3
        Case 01 [manage_tasks]: tool=manage_tasks errored=True survived=True
        Case 05 [convert_units]: tool=convert_units errored=True survived=True
        Case 08 [get_weather]: tool=get_weather errored=True survived=True
    prompt_c_positive  (3 case(s), tools: convert_units, get_weather, manage_tasks)
      Graceful degradation:       3/3
        Case 01 [manage_tasks]: tool=manage_tasks errored=True survived=True
        Case 05 [convert_units]: tool=convert_units errored=True survived=True
        Case 08 [get_weather]: tool=get_weather errored=True survived=True

  Saved → eval_results.json