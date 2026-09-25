The command 'cgitsync memrory reboot' archives the 'project-name' branch of the gitRepo .memory by renaming the branch itself or copying it and closing it.

After the operation the gitRepo is left without any 'project-name' branch. It is then impossible to reload a project based on .memory 'project-branch' 

The memory reboot must archive the branch and clean the 'project-name' branch from everything else than its .cgs so that the project-name.cgs remains callable from anywhere else. The command must not 'kill' the branch even if it leaves it empty when it doesn't contain any .cgs 