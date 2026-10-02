export type GradesData = {
  courseName: string;
  readOnlyFields: string[];
  canEdit: boolean;
  urls: {database: string; updateScore: string; updateComment: string; overrideGrade: string; clearGradeOverride: string};
};
export type TaskMeta = {name: string; group: string; group_start: string; score: number};
export type StudentRow = {
  username: string;
  scores: Record<string, number>;
  first_name?: string;
  last_name?: string;
  repo_url?: string;
  is_admin?: boolean;
  comment?: string | null;
  total_score: number;
  percent: number;
  large_count: number;
  grade: number | null;
  grade_is_override?: boolean;
};
export type GradesResponse = {tasks: TaskMeta[]; students: StudentRow[]; max_score?: number};
