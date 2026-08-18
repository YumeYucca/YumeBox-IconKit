export interface Env {
  ICON_BUNDLES: R2Bucket;
  GITHUB_TOKEN: string;
  GITHUB_OWNER: string;
  GITHUB_REPO: string;
  GITHUB_WORKFLOW: string;
  GITHUB_REF: string;
  ALLOWED_ORIGINS?: string;
}

type JobStatus = "queued" | "running" | "succeeded" | "failed";
type Job = {
  downloadToken: string;
  callbackToken: string;
  createdAt: string;
  expiresAt: string;
  bundleExpiresAt: string;
  status: JobStatus;
  actionsUrl?: string;
  artifactName?: string;
};

const MAX_BUNDLE_BYTES = 8 * 1024 * 1024;
const BUNDLE_TTL_SECONDS = 15 * 60;
const JOB_TTL_SECONDS = 24 * 60 * 60;

function jobKey(jobId: string) {
  return `jobs/${jobId}/job.json`;
}

async function getJob(env: Env, jobId: string): Promise<Job | undefined> {
  const object = await env.ICON_BUNDLES.get(jobKey(jobId));
  if (!object) return undefined;
  const job = await object.json<Job>();
  if (Date.parse(job.expiresAt) >= Date.now()) return job;
  await Promise.all([
    env.ICON_BUNDLES.delete(jobKey(jobId)),
    env.ICON_BUNDLES.delete(`jobs/${jobId}/icon-bundle.zip`),
  ]);
  return undefined;
}

function putJob(env: Env, jobId: string, job: Job) {
  return env.ICON_BUNDLES.put(jobKey(jobId), JSON.stringify(job), {
    httpMetadata: { contentType: "application/json" },
  });
}

function cors(request: Request, env: Env): Headers {
  const headers = new Headers({ Vary: "Origin" });
  const origin = request.headers.get("Origin");
  if (origin && allowedOrigin(request, env, origin)) {
    headers.set("Access-Control-Allow-Origin", origin);
    headers.set("Access-Control-Allow-Methods", "POST, OPTIONS");
    headers.set("Access-Control-Allow-Headers", "Content-Type");
  }
  return headers;
}

function allowedOrigin(request: Request, env: Env, origin: string): boolean {
  const configured =
    env.ALLOWED_ORIGINS?.split(",").map((value) => value.trim()) ?? [];
  return origin === new URL(request.url).origin || configured.includes(origin);
}

function response(
  request: Request,
  env: Env,
  body: BodyInit | null,
  init: ResponseInit = {},
) {
  const headers = cors(request, env);
  new Headers(init.headers).forEach((value, key) => headers.set(key, value));
  return new Response(body, { ...init, headers });
}

function randomToken(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}

function safeEqual(left: string, right: string): boolean {
  if (left.length !== right.length) return false;
  let result = 0;
  for (let index = 0; index < left.length; index += 1)
    result |= left.charCodeAt(index) ^ right.charCodeAt(index);
  return result === 0;
}

async function dispatchBuild(
  env: Env,
  jobId: string,
  downloadToken: string,
  callbackToken: string,
  workerUrl: string,
): Promise<void> {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/actions/workflows/${env.GITHUB_WORKFLOW}/dispatches`;
  const githubResponse = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      "User-Agent": "yumebox-iconkit",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ref: env.GITHUB_REF,
      inputs: {
        job_id: jobId,
        download_token: downloadToken,
        callback_token: callbackToken,
        worker_url: workerUrl,
      },
    }),
  });
  if (!githubResponse.ok) {
    const detail = (await githubResponse.text())
      .replaceAll(/\s+/g, " ")
      .slice(0, 300);
    throw new Error(
      `GitHub dispatch failed with ${githubResponse.status}: ${detail || "no details"}`,
    );
  }
}

export default {
  async fetch(request, env): Promise<Response> {
    const url = new URL(request.url);
    if (request.method === "OPTIONS")
      return response(request, env, null, { status: 204 });

    if (request.method === "POST" && url.pathname === "/v1/jobs") {
      const origin = request.headers.get("Origin");
      if (!origin || !allowedOrigin(request, env, origin))
        return response(request, env, "Forbidden", { status: 403 });

      const form = await request.formData();
      const bundle = form.get("bundle");
      if (
        !(bundle instanceof File) ||
        bundle.size === 0 ||
        bundle.size > MAX_BUNDLE_BYTES
      ) {
        return response(
          request,
          env,
          "Bundle must be a ZIP smaller than 8 MB",
          { status: 400 },
        );
      }
      const bytes = await bundle.arrayBuffer();
      if (new Uint8Array(bytes, 0, 4).join(",") !== "80,75,3,4") {
        return response(request, env, "Bundle is not a ZIP archive", {
          status: 400,
        });
      }

      const jobId = crypto.randomUUID();
      const downloadToken = randomToken();
      const callbackToken = randomToken();
      const objectKey = `jobs/${jobId}/icon-bundle.zip`;
      await env.ICON_BUNDLES.put(objectKey, bytes, {
        httpMetadata: { contentType: "application/zip" },
        customMetadata: { jobId },
      });
      await putJob(env, jobId, {
        downloadToken,
        callbackToken,
        createdAt: new Date().toISOString(),
        expiresAt: new Date(Date.now() + JOB_TTL_SECONDS * 1000).toISOString(),
        bundleExpiresAt: new Date(
          Date.now() + BUNDLE_TTL_SECONDS * 1000,
        ).toISOString(),
        status: "queued",
      } satisfies Job);

      try {
        await dispatchBuild(
          env,
          jobId,
          downloadToken,
          callbackToken,
          url.origin,
        );
      } catch (error) {
        await Promise.all([
          env.ICON_BUNDLES.delete(objectKey),
          env.ICON_BUNDLES.delete(jobKey(jobId)),
        ]);
        return response(
          request,
          env,
          error instanceof Error ? error.message : "Failed to dispatch build",
          { status: 502 },
        );
      }

      return response(
        request,
        env,
        JSON.stringify({
          jobId,
          statusUrl: `/v1/jobs/${jobId}`,
        }),
        { status: 202, headers: { "Content-Type": "application/json" } },
      );
    }

    const statusMatch = url.pathname.match(/^\/v1\/jobs\/([\w-]+)$/);
    if (request.method === "GET" && statusMatch) {
      const job = await getJob(env, statusMatch[1]);
      if (!job) return response(request, env, "Not found", { status: 404 });
      return response(
        request,
        env,
        JSON.stringify({
          status: job.status,
          actionsUrl: job.actionsUrl,
          artifactName: job.artifactName,
        }),
        {
          headers: {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
          },
        },
      );
    }

    const callbackMatch = url.pathname.match(
      /^\/v1\/jobs\/([\w-]+)\/callback$/,
    );
    if (request.method === "POST" && callbackMatch) {
      const job = await getJob(env, callbackMatch[1]);
      if (!job) return new Response("Not found", { status: 404 });
      const token =
        request.headers.get("Authorization")?.replace(/^Bearer\s+/, "") ?? "";
      if (!safeEqual(token, job.callbackToken))
        return new Response("Forbidden", { status: 403 });
      const payload = (await request.json()) as Partial<{
        status: JobStatus;
        actionsUrl: string;
        artifactName: string;
      }>;
      if (
        !payload.status ||
        !["running", "succeeded", "failed"].includes(payload.status)
      )
        return new Response("Invalid status", { status: 400 });
      if (
        !payload.actionsUrl?.startsWith(
          `https://github.com/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/actions/runs/`,
        )
      )
        return new Response("Invalid Actions URL", { status: 400 });
      await putJob(env, callbackMatch[1], {
        ...job,
        status: payload.status,
        actionsUrl: payload.actionsUrl,
        artifactName: payload.artifactName,
      } satisfies Job);
      return new Response(null, { status: 204 });
    }

    const match = url.pathname.match(/^\/v1\/jobs\/([\w-]+)\/bundle$/);
    if (request.method === "GET" && match) {
      const jobId = match[1];
      const token = url.searchParams.get("token") ?? "";
      const job = await getJob(env, jobId);
      if (!job) return new Response("Not found", { status: 404 });
      if (!safeEqual(token, job.downloadToken))
        return new Response("Forbidden", { status: 403 });
      if (Date.parse(job.bundleExpiresAt) < Date.now()) {
        await env.ICON_BUNDLES.delete(`jobs/${jobId}/icon-bundle.zip`);
        return new Response("Bundle expired", { status: 410 });
      }

      const objectKey = `jobs/${jobId}/icon-bundle.zip`;
      const bundle = await env.ICON_BUNDLES.get(objectKey);
      if (!bundle) return new Response("Not found", { status: 404 });
      await env.ICON_BUNDLES.delete(objectKey);
      return new Response(bundle.body, {
        headers: { "Content-Type": "application/zip" },
      });
    }

    return response(request, env, "Not found", { status: 404 });
  },
} satisfies ExportedHandler<Env>;
