There are a lot of *.cgs in .cgitsync/.memory/.state. This is wrong because the only Reference in ComplexGitSync is the GitTree. state is a GitTree Snapshot called .gts. .cgs is the only input format, that discribe a project with its parent. It is an input file for ComplexGitSync and do not reference necesseraly the whole tree. Those files must not appear in state. gts is the core object, cgs is an API format for describing a GitTree


Another reinforcement is to clarify the frontier between initialise and bootstrap. They do have a lot in common. I propose that initialise corresponds to a nested install, so no install name only the default ../.. for CGSPATH, and CGSHOME=$CGSPATH/Project_name; and bootstrap for a standalone install.

It will therefore be possible to administrate with a standalone approach a project that incorporates a local nested cgitsync
