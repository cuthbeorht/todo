"""An AWS Python Pulumi program"""

import pulumi
import pulumi_aws as aws
import datetime

health_api_gateway_log_group = aws.cloudwatch.LogGroup(
    "health_api_gateway_log_group",
    name="health_api"
)

cloudwatch_role = aws.iam.Role("cloudwatchRole", assume_role_policy="""{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "",
      "Effect": "Allow",
      "Principal": {
        "Service": "apigateway.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
""")

# Create Health AWS Lambda

iam_for_health_lambda = aws.iam.Role(
    "iamHealthLambda",
    assume_role_policy="""{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Principal": {
                    "Service": "lambda.amazonaws.com"
                },
                "Effect": "Allow",
                "Sid": ""             
            }
        ]
    }
    """
)

cloudwatch_role_policy = aws.iam.RolePolicy("cloudwatchRolePolicy",
                                            role=cloudwatch_role.id,
                                            policy="""{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:DescribeLogGroups",
                "logs:DescribeLogStreams",
                "logs:PutLogEvents",
                "logs:GetLogEvents",
                "logs:FilterLogEvents"
            ],
            "Resource": "*"
        }
    ]
}
""")

health_api_gateway_account = aws.apigateway.Account(
    "health_api_gateway_account",
    cloudwatch_role_arn=cloudwatch_role.arn
)


policy_for_health_lambda_logging = aws.iam.Policy(
    "health_api_gateway_lambda_loggin_policy",
    path="/",
    description="IAM policy for logging from a lambda",
    policy="""{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Action": [
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:PutLogEvents"
          ],
          "Resource": "arn:aws:logs:*:*:*",
          "Effect": "Allow"
        }
      ]
    }
    """
)

# Attach logging policy to IAM Role
health_api_gateway_logging_policy_attachment = aws.iam.RolePolicyAttachment(
    "health_api_gateway_logging",
    role=iam_for_health_lambda.name,
    policy_arn=policy_for_health_lambda_logging.arn
)

health_lambda = aws.lambda_.Function(
    "healthLambda",
    code=pulumi.FileArchive("../../dist/lambda.zip"),
    role=iam_for_health_lambda.arn,
    handler="app.lambda.handler",
    runtime="python3.8",
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "foo": "bar"
        }
    ),
    opts=pulumi.ResourceOptions(depends_on=[
                                health_api_gateway_logging_policy_attachment, health_api_gateway_log_group])
)


health_api_gateway = aws.apigateway.RestApi(
    "health_apigateway",

)


health_api_gateway_resource = aws.apigateway.Resource(
    "health_api_gateway_resource",
    args=aws.apigateway.ResourceArgs(
        parent_id=health_api_gateway.root_resource_id,
        rest_api=health_api_gateway.id,
        path_part="{proxy+}"
    )
)

health_api_gateway_method = aws.apigateway.Method(
    "health_api_gateway_method",
    args=aws.apigateway.MethodArgs(
        authorization="NONE",
        http_method="ANY",
        resource_id=health_api_gateway_resource.id,
        rest_api=health_api_gateway.id
    )
)

health_lambda_permission = aws.lambda_.Permission(
    "allow_health_api_gateway",
    args=aws.lambda_.PermissionArgs(
        action="lambda:InvokeFunction",
        function=health_lambda.name,
        principal="apigateway.amazonaws.com",
        source_arn=health_api_gateway.execution_arn.apply(
            lambda execution_arn: f"{execution_arn}/*/*/*")
    )
)

health_api_gateway_integration = aws.apigateway.Integration(
    "health_api_gateway_integration",
    args=aws.apigateway.IntegrationArgs(
        rest_api=health_api_gateway.id,
        resource_id=health_api_gateway_resource.id,
        http_method=health_api_gateway_method.http_method,
        type="AWS_PROXY",
        integration_http_method="POST",
        uri=health_lambda.invoke_arn
    )
)

health_api_gateway_deployment = aws.apigateway.Deployment(
    "health_deployment",
    rest_api=health_api_gateway.id,
    triggers={
        "date": str(datetime.datetime.now())
    },
    opts=pulumi.ResourceOptions(
        depends_on=[health_api_gateway_method, health_api_gateway_integration])
)

health_api_gateway_stage = aws.apigateway.Stage(
    "health_api_gateway_stage",
    deployment=health_api_gateway_deployment.id,
    rest_api=health_api_gateway.id,
    stage_name="test",
    xray_tracing_enabled=True
)

health_api_gateway_method_settings = aws.apigateway.MethodSettings(
    "health_api_gateway_method_settings_all",
    rest_api=health_api_gateway.id,
    stage_name=health_api_gateway_stage.stage_name,
    method_path="*/*",
    settings=aws.apigateway.MethodSettingsSettingsArgs(
        metrics_enabled=True,
        logging_level="INFO"
    )
)
