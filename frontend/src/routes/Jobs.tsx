import { JobsTable } from "@/components/JobsTable";

export function Jobs() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Jobs</h1>
      <JobsTable />
    </div>
  );
}
