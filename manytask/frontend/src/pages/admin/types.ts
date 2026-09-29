export type AdminUser = {id: number; username: string; firstName: string; lastName: string; instanceAdmin: boolean};
export type NamespaceSummary = {id: number; name: string; slug: string; description: string; gitlabGroupId: number | null; usersCount: number; coursesCount?: number; href: string};
export type InstanceAdminData = {action: string; users: AdminUser[]; namespaces: NamespaceSummary[]; namespaceApiUrl: string; namespacePanelUrlTemplate: string; createCourseUrl: string; courses: Array<{name: string; href: string; namespaceSlug: string}>};
export type NamespacesData = {namespaces: NamespaceSummary[]};
export type NamespaceUser = {id: number; username: string; rmsId: number | string; role: string};
export type UserCandidate = {id: number; username: string; rmsId?: number | string};
export type NamespaceData = {namespace: NamespaceSummary; users: NamespaceUser[]; availableUsers: UserCandidate[]; courses: Array<{id: number; name: string; href: string; owners: string; status: string; gitlabGroup: string; editHref: string}>; usersUrl: string; roles: Array<{value: string; label: string}>; createCourseUrl: string; namespacesUrl: string};
export const adminRoles = [{value: 'namespace_admin', label: 'Namespace Admin'}, {value: 'program_manager', label: 'Program Manager'}];
