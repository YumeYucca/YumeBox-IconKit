export interface Env {
  ICON_BUNDLES: R2Bucket;
  GITHUB_OWNER: string;
  GITHUB_REPO: string;
  ALLOWED_ORIGINS?: string;
}

type Job = {
  downloadToken: string;
  createdAt: string;
  expiresAt: string;
  bundleExpiresAt: string;
};

const MAX_BUNDLE_BYTES = 8 * 1024 * 1024;
// The GitHub runner may wait in the queue before preparing Android build tools.
const BUNDLE_TTL_SECONDS = 60 * 60;
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

function issueUrl(env: Env, workerUrl: string, jobId: string, token: string): string {
  const bundleUrl = `${workerUrl}/v1/jobs/${jobId}/bundle?token=${token}`;
  const search = new URLSearchParams({
    template: "icon-build.md",
    title: "[IconKit] Build APK",
    body: [
      "## IconKit APK 构建请求",
      "此 Issue 由 IconKit 自动创建。请勿修改下方图标包链接，构建将自动开始。",
      `\`\`\`text\n${bundleUrl}\n\`\`\``,
    ].join("\n\n"),
  });
  return `https://github.com/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/issues/new?${search}`;
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
      const objectKey = `jobs/${jobId}/icon-bundle.zip`;
      await env.ICON_BUNDLES.put(objectKey, bytes, {
        httpMetadata: { contentType: "application/zip" },
        customMetadata: { jobId },
      });
      await putJob(env, jobId, {
        downloadToken,
        createdAt: new Date().toISOString(),
        expiresAt: new Date(Date.now() + JOB_TTL_SECONDS * 1000).toISOString(),
        bundleExpiresAt: new Date(
          Date.now() + BUNDLE_TTL_SECONDS * 1000,
        ).toISOString(),
      } satisfies Job);

      return response(
        request,
        env,
        JSON.stringify({
          issueUrl: issueUrl(env, url.origin, jobId, downloadToken),
        }),
        { status: 202, headers: { "Content-Type": "application/json" } },
      );
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
      return new Response(bundle.body, {
        headers: { "Content-Type": "application/zip" },
      });
    }

    return response(request, env, "Not found", { status: 404 });
  },
} satisfies ExportedHandler<Env>;
