# Hints — 04

1. Separate the caller's authorization to invoke the simulator from the simulated role's permissions.
2. Which exact resource ARN is being evaluated? What resource types do `GetObject` and `ListBucket` accept?
3. Compare the requested object's ARN to both policy Resource strings. An identity allow and a boundary allow must overlap for this exercise.
