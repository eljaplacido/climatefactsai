import { useState, useEffect } from "react";
import { Play, RefreshCw, Activity, Clock, CheckCircle2 } from "lucide-react";
import StatCard from "../components/StatCard";
import LoadingSpinner from "../components/LoadingSpinner";
import { api } from "../services/api";
import type { DashboardStats, WorkflowStatus } from "../types";
import { format } from "date-fns";
import { enGB } from "date-fns/locale";

function AdminDashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [workflows, setWorkflows] = useState<WorkflowStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [triggerMessage, setTriggerMessage] = useState<string | null>(null);

  useEffect(() => {
    loadDashboardData();

    const interval = setInterval(loadDashboardData, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadDashboardData = async () => {
    try {
      const [statsData, workflowsData] = await Promise.all([
        api.getAdminDashboard(),
        api.getWorkflows(10),
      ]);

      setStats(statsData);
      setWorkflows(workflowsData);
    } catch (error) {
      console.error("Error loading dashboard:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerWorkflow = async () => {
    setTriggering(true);
    setTriggerMessage(null);

    try {
      const result = await api.triggerWorkflow();
      setTriggerMessage(`Workflow started (task id: ${result.task_id})`);
      setTimeout(loadDashboardData, 2000);
    } catch (error) {
      setTriggerMessage("Unable to trigger workflow. Please try again.");
      console.error("Error triggering workflow:", error);
    } finally {
      setTriggering(false);
    }
  };

  if (loading) {
    return <LoadingSpinner text="Loading admin dashboard..." />;
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Operations dashboard</h1>
          <p className="text-gray-600 mt-1">System health and workflow control</p>
        </div>

        <button
          onClick={loadDashboardData}
          className="flex items-center space-x-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
        >
          <RefreshCw className="h-5 w-5" />
          <span>Refresh</span>
        </button>
      </div>

      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard title="Total articles" value={stats.total_articles} icon={Activity} color="blue" />
          <StatCard title="Published today" value={stats.articles_today} icon={Clock} color="green" />
          <StatCard title="Fact checks" value={stats.total_fact_checks} icon={CheckCircle2} color="purple" />
          <StatCard title="Verified claims" value={stats.verified_claims} icon={CheckCircle2} color="orange" />
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Workflow control</h2>

        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div>
              <h3 className="font-medium text-gray-900">Kick off the pipeline manually</h3>
              <p className="text-sm text-gray-600 mt-1">
                Triggers ingestion, fact checks, summarisation, and publication tasks.
              </p>
            </div>

            <button
              onClick={handleTriggerWorkflow}
              disabled={triggering}
              className="flex items-center space-x-2 px-6 py-3 bg-climate-green-600 text-white rounded-lg hover:bg-climate-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
            >
              <Play className="h-5 w-5" />
              <span>{triggering ? "Starting..." : "Start workflow"}</span>
            </button>
          </div>

          {triggerMessage && (
            <div
              className={`p-4 rounded-lg ${
                triggerMessage.startsWith("Workflow started")
                  ? "bg-green-50 text-green-800"
                  : "bg-red-50 text-red-800"
              }`}
            >
              {triggerMessage}
            </div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-6">Workflow history</h2>

        {workflows.length === 0 ? (
          <p className="text-gray-500 text-center py-8">No pipeline executions recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Task ID</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Status</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Stage</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Started</th>
                </tr>
              </thead>
              <tbody>
                {workflows.map((workflow) => (
                  <tr key={workflow.task_id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <code className="text-sm font-mono text-gray-900">{workflow.task_id}</code>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          workflow.status === "COMPLETED"
                            ? "bg-green-100 text-green-800"
                            : workflow.status === "FAILED"
                            ? "bg-red-100 text-red-800"
                            : "bg-yellow-100 text-yellow-800"
                        }`}
                      >
                        {workflow.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-600">
                      {workflow.current_stage || "-"}
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-600">
                      {workflow.started_at
                        ? format(new Date(workflow.started_at), "dd MMM yyyy HH:mm", { locale: enGB })
                        : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">System info</h3>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-600">API version</dt>
              <dd className="font-medium text-gray-900">1.0.0</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Environment</dt>
              <dd className="font-medium text-gray-900">Development</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Last update</dt>
              <dd className="font-medium text-gray-900">
                {stats?.last_updated
                  ? format(new Date(stats.last_updated), "dd MMM yyyy HH:mm", { locale: enGB })
                  : "-"}
              </dd>
            </div>
          </dl>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Agents</h3>
          <div className="space-y-3">
            {["Orchestrator", "Content discovery", "Fact-checking", "Content creation"].map((agent) => (
              <div key={agent} className="flex items-center justify-between">
                <span className="text-sm text-gray-700">{agent}</span>
                <span className="flex items-center space-x-1 text-sm text-green-600">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span>Online</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminDashboard;
