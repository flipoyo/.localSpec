Again a problem with memory that doesn't have an upstream branch, after
checkout memory-dev, which is not the case for main. The branch was
existing. I suspect there are still exceptions in the code about .memory
that shouldn't exist anymore because it is now only a private/local repo.
Audit and write a ticket for fixing the bug.

Follow-up: the first analysis was awkward — it did not explain why the
same problem is not seen for the other two private/local repos
(.localSpec, .claude). Persisted in wanting a clear analysis of what is
actually specific to .memory versus the other private/local repos, with
those specificities erased as much as possible. Suggested that checkout
could include a fetch when one has not already been done, and asked
whether .memory itself is a good reference for checking that information.
