merge --all memory-dev --into main failed partway through: it checked out
docs/.localSpec/.claude onto main, then hit .memory (.cgitsync) and
aborted, because .memory's worktree is never actually clean at the git
level — .cgitsync is both the memory's git repo and cgitsync's own live
state directory (lgr/, state/, logs/, commit-logs/ all get written by
every command), so `git checkout` on it fails for real, not just
cosmetically.

Do not exclude .memory from private/local scope for merge/checkout/tag
the way add/commit/push/pull were excluded. Instead: create a .working
area that is the actual heart of the fix. The frontier between .memory
and .working is exactly the frontier between what is and what will be.
.working is a transition state between two memory syncs that leads to a
new stable .memory state. It is not part of what is merged, added, or
pushed — it is what becomes the next .memory increment for the next
action on the GitTree.
