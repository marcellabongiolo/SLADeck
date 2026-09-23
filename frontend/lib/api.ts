const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type TokenPair = { access_token: string; refresh_token: string; token_type: string; expires_in: number };
export type User = { id: string; email: string; full_name: string; created_at: string };
export type Organization = { id: string; name: string; slug: string; created_at: string };
export type Membership = { user_id: string; email: string; full_name: string; role: "owner"|"admin"|"manager"|"member"; created_at: string };
export type RequestItem = {
  id:string; organization_id:string; title:string; description:string;
  status:"open"|"in_progress"|"waiting"|"resolved"|"closed";
  priority:"low"|"normal"|"high"|"urgent"; requester_id:string; assignee_id:string|null;
  sla_policy_id:string|null; first_response_due_at:string|null; first_responded_at:string|null;
  resolution_due_at:string|null; resolved_at:string|null; created_at:string; updated_at:string; sla_state:string;
};
export type SLAPolicy = {id:string;organization_id:string;name:string;first_response_minutes:number;resolution_minutes:number;created_at:string;updated_at:string};
export type Comment = {id:string;organization_id:string;request_id:string;author_id:string;body:string;created_at:string};
export type Activity = {kind:string;id:string;actor_user_id:string|null;event_type?:string;body?:string;data:Record<string,unknown>;created_at:string};

async function request<T>(path:string,init:RequestInit={},token?:string):Promise<T>{
 const response=await fetch(`${API_URL}${path}`,{...init,headers:{"Content-Type":"application/json",...(init.headers??{}),...(token?{Authorization:`Bearer ${token}`}:{})}});
 if(!response.ok){let detail="Request failed";try{detail=((await response.json()) as {detail?:string}).detail??detail}catch{} throw new Error(detail)}
 if(response.status===204)return undefined as T;
 return (await response.json()) as T;
}
export const register=(p:{email:string;full_name:string;password:string})=>request<User>("/auth/register",{method:"POST",body:JSON.stringify(p)});
export const login=(email:string,password:string)=>request<TokenPair>("/auth/login",{method:"POST",body:JSON.stringify({email,password})});
export const me=(t:string)=>request<User>("/auth/me",{},t);
export const organizations=(t:string)=>request<Organization[]>("/organizations",{},t);
export const createOrganization=(t:string,p:{name:string;slug:string})=>request<Organization>("/organizations",{method:"POST",body:JSON.stringify(p)},t);
export const members=(t:string,org:string)=>request<Membership[]>(`/organizations/${org}/members`,{},t);
export const policies=(t:string,org:string)=>request<SLAPolicy[]>(`/organizations/${org}/sla-policies`,{},t);
export const requests=(t:string,org:string,q?:{status?:string;priority?:string;assignee_id?:string})=>{
 const params=new URLSearchParams(); Object.entries(q??{}).forEach(([k,v])=>v&&params.set(k,v));
 return request<RequestItem[]>(`/organizations/${org}/requests${params.size?`?${params}`:""}`,{},t);
};
export const getRequest=(t:string,org:string,id:string)=>request<RequestItem>(`/organizations/${org}/requests/${id}`,{},t);
export const createRequest=(t:string,org:string,p:object)=>request<RequestItem>(`/organizations/${org}/requests`,{method:"POST",body:JSON.stringify(p)},t);
export const updateRequest=(t:string,org:string,id:string,p:object)=>request<RequestItem>(`/organizations/${org}/requests/${id}`,{method:"PATCH",body:JSON.stringify(p)},t);
export const firstResponse=(t:string,org:string,id:string)=>request<RequestItem>(`/organizations/${org}/requests/${id}/first-response`,{method:"POST"},t);
export const comments=(t:string,org:string,id:string)=>request<Comment[]>(`/organizations/${org}/requests/${id}/comments`,{},t);
export const addComment=(t:string,org:string,id:string,body:string)=>request<Comment>(`/organizations/${org}/requests/${id}/comments`,{method:"POST",body:JSON.stringify({body})},t);
export const activity=(t:string,org:string,id:string)=>request<Activity[]>(`/organizations/${org}/requests/${id}/activity`,{},t);
