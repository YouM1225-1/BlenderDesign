# Official Blender MCP downstream patch series

Fixed upstream base: `4309a39646e644261624bfcd2bca669b343b7621`.

The build applies these patches in order and rejects a changed patch digest or
post-patch source tree. The resulting source tree SHA-256 is
`912ed324426181d308b1fd704fe0bcffa0743ee12725c6bfaab5744962392d07`.

1. `0001-server-hardening.patch`
   (`3f925dd5d561527000cd151135a69949293c2d69f2155ed8dc037fb4a19dabf0`)
   restores bounded background execution, private snapshot identity checks,
   direct disk summaries, Retina scaling, 120-second I/O deadlines, and MCP
   1.28/2.x compatibility. It removes the HTTP transport so arbitrary-Python
   tools are available only through local STDIO and retains the upstream
   screenshot-envelope fix.
2. `0002-addon-transport-hardening.patch`
   (`dc2f46a067fa8a239c4e184e701f44e54bb9ac3efd898e53c2f90aabaafcc344`)
   restores bounded clients, fair accept/write budgets, chunked non-blocking
   responses, deferred JSON normalization, and defensive socket cleanup.
3. `0003-operation-policy.patch`
   (`c3ad53d5874ea84794559085dccd9a4d54f6019de47605597d6a47669b8e3901`)
   retains the reviewed live/background routing and visible staged-modeling
   guidance from the currently certified distribution.
4. `0004-certification-tests.patch`
   (`e49e195a648d042ca4ad8a0c3e12d09a8d2503c065474ce3b03d260eb424f289`)
   refreshes the frozen tool-description catalog, exercises the MCP 1.28/2.x
   compatibility boundary, and proves HTTP startup is rejected.
5. `0005-sdk-neutral-tests.patch`
   (`83474bc90f444499b181354cb8d2cdba914efe6958b2907329261abcca7bd00d`)
   makes the functional test clients accept the MCP 1.28 camelCase and MCP 2.x
   snake_case result-field spellings through one explicit compatibility shim.
6. `0006-source-quality-gates.patch`
   (`423c3b36261fde09c3b2df61af9c911cc91b8018e0bd2dd5bcf3bb679eccbf24`)
   makes the upstream Ruff/Mypy/Vulture/license/ASCII/namespace checks
   self-contained and SDK-version neutral.
7. `0007-bound-interactive-response-memory.patch`
   (`321c23c8d1ae232c8884d0c17e44259c827e6037be49098b90994d4caffdf89f`)
   caps captured console output, serialized add-on responses, and MCP client
   receive buffers, and rejects oversized or unterminated response frames.
8. `0008-blender-52-eevee.patch`
   (`b1a1812290ee8b40590a7b23e1bc544d59d30e40fac5dab4dd8f7c2fbf26abc1`)
   targets Blender 5.2's `BLENDER_EEVEE` engine in thumbnail rendering before
   source hashing and wheel construction.
9. `0009-bound-chat-client-http.patch`
   (`a0c417189bc7a5677cc3a535cff074d15b1da739766040447945618319b317ee`)
   restricts chat-client requests and pre-open redirects to HTTP(S), applies a
   30-second timeout, and caps response bodies at 16 MiB.
10. `0010-fix-python-api-member-lookup.patch`
    (`c20cd9b42c9ee6872b09c462822e61de1b39c85670a4b82575e203b2d4953aa8`)
    resolves members nested under the class container in per-class API RST
    files and retains an end-to-end regression for `Scene.frame_current`.

Review with `git apply --stat <patch>` and `git apply --check <patch>` from a
clean checkout of the fixed upstream base.
