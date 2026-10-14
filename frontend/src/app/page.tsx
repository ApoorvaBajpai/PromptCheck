"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, Project, PromptItem, TestCase, Run } from "@/lib/api";
import { useAuth } from "@/components/providers";
import { Navbar } from "@/components/navbar";
import { ProjectList } from "@/components/projects/project-list";
import { ProjectDashboard } from "@/components/projects/project-dashboard";
import LoginPage from "./login/page";
import { Loader2 } from "lucide-react";

export default function Home() {
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);

  // 1. Fetch user projects with TanStack Query
  const {
    data: projects = [],
    isLoading: isProjectsLoading,
    refetch: refetchProjects,
  } = useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: api.listProjects,
    enabled: isAuthenticated,
  });

  const selectedProject = projects.find((p) => p.id === selectedProjectId) || null;

  // 2. Fetch project details when a project is selected
  const {
    data: prompts = [],
    isLoading: isPromptsLoading,
    refetch: refetchPrompts,
  } = useQuery<PromptItem[]>({
    queryKey: ["prompts", selectedProjectId],
    queryFn: () => api.listPrompts(selectedProjectId!),
    enabled: !!selectedProjectId,
  });

  const {
    data: testCases = [],
    isLoading: isTestsLoading,
    refetch: refetchTests,
  } = useQuery<TestCase[]>({
    queryKey: ["test-cases", selectedProjectId],
    queryFn: () => api.listTestCases(selectedProjectId!, true),
    enabled: !!selectedProjectId,
  });

  const {
    data: runs = [],
    isLoading: isRunsLoading,
    refetch: refetchRuns,
  } = useQuery<Run[]>({
    queryKey: ["runs", selectedProjectId],
    queryFn: () => api.listRuns(selectedProjectId!),
    enabled: !!selectedProjectId,
  });

  const handleRefreshAll = () => {
    refetchProjects();
    if (selectedProjectId) {
      refetchPrompts();
      refetchTests();
      refetchRuns();
    }
  };

  // Auth loading state
  if (isAuthLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  // Not authenticated -> show Login / Register
  if (!isAuthenticated) {
    return <LoginPage />;
  }

  const [dashboardTab, setDashboardTab] = useState<"prompts" | "tests" | "runs" | "settings">("prompts");

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col text-slate-100">
      <Navbar
        currentProject={selectedProject}
        onSelectProjectList={() => setSelectedProjectId(null)}
        onOpenSettings={() => setDashboardTab("settings")}
      />

      <main className="flex-1 pb-16">
        {!selectedProject ? (
          <ProjectList
            projects={projects}
            isLoading={isProjectsLoading}
            onSelectProject={(p) => {
              setSelectedProjectId(p.id);
              setDashboardTab("prompts");
            }}
            onRefresh={refetchProjects}
          />
        ) : (
          <ProjectDashboard
            project={selectedProject}
            prompts={prompts}
            testCases={testCases}
            runs={runs}
            isLoading={isPromptsLoading || isTestsLoading || isRunsLoading}
            activeTab={dashboardTab}
            onTabChange={setDashboardTab}
            onRefresh={handleRefreshAll}
            onBackToProjects={() => setSelectedProjectId(null)}
          />
        )}
      </main>
    </div>
  );
}
