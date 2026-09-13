*Emitted by the owner in conversation on 2026-09-13, not as a file. Recorded
here verbatim, and closed the same day by the change that carried it out,
because the record of what was asked for should not live only in a chat log.*

---

update AgentSpec by renaiming it DevTickets. It must be part of .localSpec.
The DevTickets must contain a README.md for explaining the rationale of the
DevOrchestration : User emits a shortTickets, claude orchestrates the update
of all openTickets on user demand. Once done the shortTicket is closed and
archived in archive/.closedUserTicket/ following the same rules than
DevPlanTicket archiving. Reorganise the repos, and the .cgs with that.
install.cgs in main won't install AgentSpec anymore, it will be private only.
It is a clearer USER[DEV separation than matches the ambition of the project
to separate PROJECT(.PUBLIC) and private. Update every necessary file in the
project, including the private part. Don't forget DevGuide
