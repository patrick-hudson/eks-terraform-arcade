# Hints · routes define reachability

**Foundation:** Every subnet uses one route table, explicitly or through the VPC's main table. Every route table has a local route for the VPC CIDR. An internet gateway route alone does not assign a public IP or open a security group.

<details><summary>Hint 1 — stable shape</summary>

Discover available AZ names, then build a two-entry map keyed by `a` and `b`. Store the AZ name and numeric subnet offset in each entry. Resource addresses use those keys rather than changing list positions.
</details>

<details><summary>Hint 2 — CIDR math</summary>

`cidrsubnet("10.42.0.0/16", 8, 10)` creates `10.42.10.0/24`. Increasing the prefix length by eight produces 256 separate /24 networks from the /16. Public and private offsets must not overlap.
</details>

<details><summary>Hint 3 — associations matter</summary>

Use `aws_route_table_association` for all four subnets. Give only the public route table a separate `aws_route` to the attached internet gateway. Private tables do not need an explicit local route resource; AWS adds it.
</details>

<details><summary>Hint 4 — why no connectivity test?</summary>

This game proves configuration and requires you to explain packet flow; it does not claim to have proved host connectivity. A live ping or curl would add hosts, IPs, firewall decisions and cost that are outside the routing-only mission.
</details>
