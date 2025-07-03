# IFC Labels

## ListIssues

- owner: bytecodealliance
- repo: wasmtime
- perPage: 3


## Response

```json
{
  "id": 3197057906,
  "number": 11175,
  "state": "open",
  "locked": false,
  "title": "Remove hash tables and bump chunk from the DRC collector",
  "body": "This removes the explicit `HashSet`s used to represent the over-approximated-stack-roots and precise-stack-roots sets and replaces them with an intrusive, singly-linked list and a mark bit in the object headers respectively. The new list implementation also subsumes the old bump chunk that sat in front of the old over-approximated-stack-roots hash set.\r\n\r\nThis shaves off about 25% of the time it takes to run the test case in https://github.com/bytecodealliance/wasmtime/issues/11141 for me locally.\r\n\r\nThis also ended up being a nice simplification of the DRC collector, which in turn allowed us to further simplify the `GcHeap` trait, since we no longer ever need to GC before passing GC refs into Wasm.\r\n\r\nFixes https://github.com/bytecodealliance/wasmtime/issues/11162\r\n\r\n<!--\r\nPlease make sure you include the following information:\r\n\r\n- If this work has been discussed elsewhere, please include a link to that\r\n  conversation. If it was discussed in an issue, just mention \"issue #...\".\r\n\r\n- Explain why this change is needed. If the details are in an issue already,\r\n  this can be brief.\r\n\r\nOur development process is documented in the Wasmtime book:\r\nhttps://docs.wasmtime.dev/contributing-development-process.html\r\n\r\nPlease ensure all communication follows the code of conduct:\r\nhttps://github.com/bytecodealliance/wasmtime/blob/main/CODE_OF_CONDUCT.md\r\n-->\r\n",
  "author_association": "MEMBER",
  "user": {
    "login": "fitzgen",
    "id": 74571,
    "node_id": "MDQ6VXNlcjc0NTcx",
    "avatar_url": "https://avatars.githubusercontent.com/u/74571?v=4",
    "html_url": "https://github.com/fitzgen",
    "gravatar_id": "",
    "type": "User",
    "site_admin": false,
    "url": "https://api.github.com/users/fitzgen",
    "events_url": "https://api.github.com/users/fitzgen/events{/privacy}",
    "following_url": "https://api.github.com/users/fitzgen/following{/other_user}",
    "followers_url": "https://api.github.com/users/fitzgen/followers",
    "gists_url": "https://api.github.com/users/fitzgen/gists{/gist_id}",
    "organizations_url": "https://api.github.com/users/fitzgen/orgs",
    "received_events_url": "https://api.github.com/users/fitzgen/received_events",
    "repos_url": "https://api.github.com/users/fitzgen/repos",
    "starred_url": "https://api.github.com/users/fitzgen/starred{/owner}{/repo}",
    "subscriptions_url": "https://api.github.com/users/fitzgen/subscriptions"
  },
  "labels": [
    {
      "id": 1785771916,
      "url": "https://api.github.com/repos/bytecodealliance/wasmtime/labels/wasmtime:api",
      "name": "wasmtime:api",
      "color": "006b75",
      "description": "Related to the API of the `wasmtime` crate itself",
      "default": false,
      "node_id": "MDU6TGFiZWwxNzg1NzcxOTE2"
    },
    {
      "id": 3277291951,
      "url": "https://api.github.com/repos/bytecodealliance/wasmtime/labels/wasmtime:ref-types",
      "name": "wasmtime:ref-types",
      "color": "006b75",
      "description": "Issues related to reference types and GC in Wasmtime",
      "default": false,
      "node_id": "MDU6TGFiZWwzMjc3MjkxOTUx"
    }
  ],
  "comments": 1,
  "created_at": "2025-07-02T20:09:04Z",
  "updated_at": "2025-07-03T05:48:01Z",
  "url": "https://api.github.com/repos/bytecodealliance/wasmtime/issues/11175",
  "html_url": "https://github.com/bytecodealliance/wasmtime/pull/11175",
  "comments_url": "https://api.github.com/repos/bytecodealliance/wasmtime/issues/11175/comments",
  "events_url": "https://api.github.com/repos/bytecodealliance/wasmtime/issues/11175/events",
  "labels_url": "https://api.github.com/repos/bytecodealliance/wasmtime/issues/11175/labels{/name}",
  "repository_url": "https://api.github.com/repos/bytecodealliance/wasmtime",
  "pull_request": {
    "url": "https://api.github.com/repos/bytecodealliance/wasmtime/pulls/11175",
    "html_url": "https://github.com/bytecodealliance/wasmtime/pull/11175",
    "diff_url": "https://github.com/bytecodealliance/wasmtime/pull/11175.diff",
    "patch_url": "https://github.com/bytecodealliance/wasmtime/pull/11175.patch"
  },
  "reactions": {
    "total_count": 0,
    "+1": 0,
    "-1": 0,
    "laugh": 0,
    "confused": 0,
    "heart": 0,
    "hooray": 0,
    "rocket": 0,
    "eyes": 0,
    "url": "https://api.github.com/repos/bytecodealliance/wasmtime/issues/11175/reactions"
  },
  "node_id": "PR_kwDOBhDaXM6dJV4D",
  "draft": false
}
```

```json
{
  "id": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "number": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "state": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "state_reason": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "locked": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "title": {
    "integrity": "low",
    "confidentiality": [
      "public"
    ]
  },
  "body": {
    "integrity": "low",
    "confidentiality": [
      "public"
    ]
  },
  "author_association": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "user": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "labels": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "assignee": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "comments": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "closed_at": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "created_at": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "updated_at": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "closed_by": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "url": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "html_url": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "comments_url": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "events_url": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "labels_url": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "repository_url": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "milestone": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "pull_request": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "repository": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "reactions": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "assignees": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "node_id": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "draft": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "type": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "text_matches": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  },
  "active_lock_reason": {
    "integrity": "high",
    "confidentiality": [
      "public"
    ]
  }
}
```