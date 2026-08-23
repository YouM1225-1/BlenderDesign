# Official Blender MCP downstream patch series

Fixed upstream base: `4309a39646e644261624bfcd2bca669b343b7621`.

The build applies these patches in order and rejects a changed patch digest or
post-patch source tree. The resulting source tree SHA-256 is
`123bde66df6efb6213ecf6981720cd20e4b27cb6ffdffc3e0b232033740fcdec`.

1. `0001-server-hardening.patch`
   (`0e6457d30ae810f0ad35dfb4319adae01f88d7d997604bd48c19b54a9a063aa8`)
   restores bounded background execution, private snapshot identity checks,
   direct disk summaries, Retina scaling, 120-second I/O deadlines, and MCP
   1.28/2.x compatibility. It retains the upstream screenshot-envelope fix.
2. `0002-addon-transport-hardening.patch`
   (`bec6e59e2a1284814b57862144f9c5006d6f9e4c4b0615f9d64be4340b14151b`)
   restores bounded clients, fair accept/write budgets, chunked non-blocking
   responses, deferred JSON normalization, and defensive socket cleanup.
3. `0003-operation-policy.patch`
   (`e7be2016307d8c8e5867670aeb313716abfd93c9ba99bfe08fcde392f32493d6`)
   retains the reviewed live/background routing and visible staged-modeling
   guidance from the currently certified distribution.
4. `0004-certification-tests.patch`
   (`00ec5c42a91cd4f07b2415f5750080009e8e95098f607432afb1a77bd0555234`)
   refreshes the frozen tool-description catalog and exercises the explicit
   MCP 1.28/2.x HTTP compatibility boundary.
5. `0005-sdk-neutral-tests.patch`
   (`993c953a9944419108ad36fd888bbc285b07ebaf1472435ff9bd1b6d84fe2bda`)
   makes the functional test clients accept the MCP 1.28 camelCase and MCP 2.x
   snake_case result-field spellings through one explicit compatibility shim.
6. `0006-source-quality-gates.patch`
   (`c58b599b390cbd0de2def072f5b987c925b487f61662b35c0edf4e964850e07a`)
   makes the upstream Ruff/Mypy/Vulture/license/ASCII/namespace checks
   self-contained and SDK-version neutral.
7. `0007-bound-interactive-response-memory.patch`
   (`f8f87e108f3acaecbf28752cfe4dacb65fa25b61cfa9eb9d1f4a722c15292bcd`)
   caps captured console output, serialized add-on responses, and MCP client
   receive buffers, and rejects oversized or unterminated response frames.

Review with `git apply --stat <patch>` and `git apply --check <patch>` from a
clean checkout of the fixed upstream base.
