package openapi

import (
	"encoding/json"
	"fmt"
)

// OpenAPISpec represents an OpenAPI 3.0 specification
type OpenAPISpec struct {
	OpenAPI      string                 `json:"openapi"`
	Info         Info                   `json:"info"`
	Servers      []Server               `json:"servers,omitempty"`
	Paths        map[string]PathItem    `json:"paths"`
	Components   Components             `json:"components"`
	Security     []map[string][]string  `json:"security,omitempty"`
	Tags         []Tag                  `json:"tags,omitempty"`
	ExternalDocs *ExternalDocumentation `json:"externalDocs,omitempty"`
}

// Info contains metadata about the API
type Info struct {
	Title       string `json:"title"`
	Description string `json:"description,omitempty"`
	Version     string `json:"version"`
	Contact     *Contact `json:"contact,omitempty"`
	License     *License `json:"license,omitempty"`
}

// Contact contains contact information
type Contact struct {
	Name  string `json:"name,omitempty"`
	URL   string `json:"url,omitempty"`
	Email string `json:"email,omitempty"`
}

// License contains license information
type License struct {
	Name string `json:"name"`
	URL  string `json:"url,omitempty"`
}

// Server represents an API server
type Server struct {
	URL         string            `json:"url"`
	Description string            `json:"description,omitempty"`
	Variables   map[string]Variable `json:"variables,omitempty"`
}

// Variable represents a server variable
type Variable struct {
	Default     string   `json:"default"`
	Enum        []string `json:"enum,omitempty"`
	Description string   `json:"description,omitempty"`
}

// PathItem represents an API path
type PathItem struct {
	Get        *Operation `json:"get,omitempty"`
	Post       *Operation `json:"post,omitempty"`
	Put        *Operation `json:"put,omitempty"`
	Patch      *Operation `json:"patch,omitempty"`
	Delete     *Operation `json:"delete,omitempty"`
	Parameters []Parameter `json:"parameters,omitempty"`
}

// Operation represents an API operation
type Operation struct {
	Tags        []string              `json:"tags,omitempty"`
	Summary     string                `json:"summary"`
	Description string                `json:"description,omitempty"`
	OperationID string                `json:"operationId"`
	Parameters  []Parameter           `json:"parameters,omitempty"`
	RequestBody *RequestBody          `json:"requestBody,omitempty"`
	Responses   map[string]Response   `json:"responses"`
	Security    []map[string][]string `json:"security,omitempty"`
	Deprecated  bool                  `json:"deprecated,omitempty"`
}

// Parameter represents an API parameter
type Parameter struct {
	Name            string      `json:"name"`
	In              string      `json:"in"`
	Description     string      `json:"description,omitempty"`
	Required        bool        `json:"required"`
	Deprecated      bool        `json:"deprecated,omitempty"`
	AllowEmptyValue bool        `json:"allowEmptyValue,omitempty"`
	Schema          *Schema     `json:"schema,omitempty"`
	Style           string      `json:"style,omitempty"`
	Explode         *bool       `json:"explode,omitempty"`
	Example         interface{} `json:"example,omitempty"`
}

// RequestBody represents a request body
type RequestBody struct {
	Description string             `json:"description,omitempty"`
	Content     map[string]MediaType `json:"content"`
	Required    bool               `json:"required"`
}

// MediaType represents a media type
type MediaType struct {
	Schema   *Schema       `json:"schema,omitempty"`
	Example  interface{}   `json:"example,omitempty"`
	Examples map[string]Example `json:"examples,omitempty"`
}

// Example represents an example
type Example struct {
	Summary       string      `json:"summary,omitempty"`
	Description   string      `json:"description,omitempty"`
	Value         interface{} `json:"value,omitempty"`
	ExternalValue string      `json:"externalValue,omitempty"`
}

// Response represents an API response
type Response struct {
	Description string             `json:"description"`
	Content     map[string]MediaType `json:"content,omitempty"`
	Headers     map[string]Header    `json:"headers,omitempty"`
	Links       map[string]Link      `json:"links,omitempty"`
}

// Header represents a response header
type Header struct {
	Description string  `json:"description,omitempty"`
	Schema      *Schema `json:"schema,omitempty"`
	Required    bool    `json:"required"`
}

// Link represents a link
type Link struct {
	OperationRef string             `json:"operationRef,omitempty"`
	OperationID  string             `json:"operationId,omitempty"`
	Parameters   map[string]interface{} `json:"parameters,omitempty"`
	RequestBody  interface{}        `json:"requestBody,omitempty"`
	Description  string             `json:"description,omitempty"`
}

// Components contains reusable components
type Components struct {
	Schemas         map[string]*Schema         `json:"schemas,omitempty"`
	Responses       map[string]Response        `json:"responses,omitempty"`
	Parameters      map[string]Parameter       `json:"parameters,omitempty"`
	RequestBodies   map[string]RequestBody     `json:"requestBodies,omitempty"`
	Headers         map[string]Header          `json:"headers,omitempty"`
	SecuritySchemes map[string]SecurityScheme  `json:"securitySchemes,omitempty"`
}

// SecurityScheme represents a security scheme
type SecurityScheme struct {
	Type             string `json:"type"`
	Description      string `json:"description,omitempty"`
	Name             string `json:"name,omitempty"`
	In               string `json:"in,omitempty"`
	Scheme           string `json:"scheme,omitempty"`
	BearerFormat     string `json:"bearerFormat,omitempty"`
	Flows            *OAuthFlows `json:"flows,omitempty"`
	OpenIDConnectURL string `json:"openIdConnectUrl,omitempty"`
}

// OAuthFlows represents OAuth flows
type OAuthFlows struct {
	Implicit          *OAuthFlow `json:"implicit,omitempty"`
	Password          *OAuthFlow `json:"password,omitempty"`
	ClientCredentials *OAuthFlow `json:"clientCredentials,omitempty"`
	AuthorizationCode *OAuthFlow `json:"authorizationCode,omitempty"`
}

// OAuthFlow represents an OAuth flow
type OAuthFlow struct {
	AuthorizationURL string            `json:"authorizationUrl"`
	TokenURL         string            `json:"tokenUrl"`
	RefreshURL       string            `json:"refreshUrl,omitempty"`
	Scopes           map[string]string `json:"scopes"`
}

// Schema represents a JSON schema
type Schema struct {
	Type                 string            `json:"type,omitempty"`
	Format               string            `json:"format,omitempty"`
	Title                string            `json:"title,omitempty"`
	Description          string            `json:"description,omitempty"`
	Default              interface{}       `json:"default,omitempty"`
	Example              interface{}       `json:"example,omitempty"`
	Properties           map[string]*Schema `json:"properties,omitempty"`
	Items                *Schema           `json:"items,omitempty"`
	Required             []string          `json:"required,omitempty"`
	Enum                 []interface{}     `json:"enum,omitempty"`
	MinLength            *int              `json:"minLength,omitempty"`
	MaxLength            *int              `json:"maxLength,omitempty"`
	Pattern              string            `json:"pattern,omitempty"`
	Minimum              *float64          `json:"minimum,omitempty"`
	Maximum              *float64          `json:"maximum,omitempty"`
	ExclusiveMinimum     *bool             `json:"exclusiveMinimum,omitempty"`
	ExclusiveMaximum     *bool             `json:"exclusiveMaximum,omitempty"`
	MultipleOf           *float64          `json:"multipleOf,omitempty"`
	AllOf                []*Schema         `json:"allOf,omitempty"`
	OneOf                []*Schema         `json:"oneOf,omitempty"`
	AnyOf                []*Schema         `json:"anyOf,omitempty"`
	Not                  *Schema           `json:"not,omitempty"`
	Nullable             bool              `json:"nullable,omitempty"`
	Discriminator        *Discriminator    `json:"discriminator,omitempty"`
	ReadOnly             bool              `json:"readOnly,omitempty"`
	WriteOnly            bool              `json:"writeOnly,omitempty"`
	XML                  *XML              `json:"xml,omitempty"`
	ExternalDocs         *ExternalDocumentation `json:"externalDocs,omitempty"`
	Deprecated           bool              `json:"deprecated,omitempty"`
}

// Discriminator represents a discriminator
type Discriminator struct {
	PropertyName string            `json:"propertyName"`
	Mapping      map[string]string `json:"mapping,omitempty"`
}

// XML represents XML information
type XML struct {
	Name      string `json:"name,omitempty"`
	Namespace string `json:"namespace,omitempty"`
	Prefix    string `json:"prefix,omitempty"`
	Attribute bool   `json:"attribute,omitempty"`
	Wrapped   bool   `json:"wrapped,omitempty"`
}

// Tag represents an API tag
type Tag struct {
	Name         string                 `json:"name"`
	Description  string                 `json:"description,omitempty"`
	ExternalDocs *ExternalDocumentation `json:"externalDocs,omitempty"`
}

// ExternalDocumentation represents external documentation
type ExternalDocumentation struct {
	Description string `json:"description,omitempty"`
	URL         string `json:"url"`
}

// SpecBuilder builds an OpenAPI specification
type SpecBuilder struct {
	spec *OpenAPISpec
}

// NewSpecBuilder creates a new OpenAPI specification builder
func NewSpecBuilder(title, description, version string) *SpecBuilder {
	return &SpecBuilder{
		spec: &OpenAPISpec{
			OpenAPI: "3.0.0",
			Info: Info{
				Title:       title,
				Description: description,
				Version:     version,
			},
			Paths:      make(map[string]PathItem),
			Components: Components{
				Schemas:         make(map[string]*Schema),
				Responses:       make(map[string]Response),
				Parameters:      make(map[string]Parameter),
				RequestBodies:   make(map[string]RequestBody),
				Headers:         make(map[string]Header),
				SecuritySchemes: make(map[string]SecurityScheme),
			},
		},
	}
}

// SetContact sets the contact information
func (sb *SpecBuilder) SetContact(name, url, email string) *SpecBuilder {
	sb.spec.Info.Contact = &Contact{
		Name:  name,
		URL:   url,
		Email: email,
	}
	return sb
}

// SetLicense sets the license information
func (sb *SpecBuilder) SetLicense(name, url string) *SpecBuilder {
	sb.spec.Info.License = &License{
		Name: name,
		URL:  url,
	}
	return sb
}

// AddServer adds a server to the specification
func (sb *SpecBuilder) AddServer(url, description string) *SpecBuilder {
	sb.spec.Servers = append(sb.spec.Servers, Server{
		URL:         url,
		Description: description,
	})
	return sb
}

// AddPath adds or updates a path in the specification
func (sb *SpecBuilder) AddPath(path string, method string, operation *Operation) *SpecBuilder {
	item := sb.spec.Paths[path]

	switch method {
	case "get":
		item.Get = operation
	case "post":
		item.Post = operation
	case "put":
		item.Put = operation
	case "patch":
		item.Patch = operation
	case "delete":
		item.Delete = operation
	}

	sb.spec.Paths[path] = item
	return sb
}

// AddSchema adds a reusable schema component
func (sb *SpecBuilder) AddSchema(name string, schema *Schema) *SpecBuilder {
	sb.spec.Components.Schemas[name] = schema
	return sb
}

// AddSecurityScheme adds a security scheme
func (sb *SpecBuilder) AddSecurityScheme(name string, scheme SecurityScheme) *SpecBuilder {
	sb.spec.Components.SecuritySchemes[name] = scheme
	return sb
}

// AddTag adds a tag to the specification
func (sb *SpecBuilder) AddTag(tag Tag) *SpecBuilder {
	sb.spec.Tags = append(sb.spec.Tags, tag)
	return sb
}

// SetExternalDocs sets the external documentation
func (sb *SpecBuilder) SetExternalDocs(description, url string) *SpecBuilder {
	sb.spec.ExternalDocs = &ExternalDocumentation{
		Description: description,
		URL:         url,
	}
	return sb
}

// Build returns the OpenAPI specification as JSON
func (sb *SpecBuilder) Build() ([]byte, error) {
	return json.MarshalIndent(sb.spec, "", "  ")
}

// BuildPretty returns the OpenAPI specification as formatted JSON
func (sb *SpecBuilder) BuildPretty() (string, error) {
	data, err := sb.Build()
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// GetSpec returns the underlying OpenAPI specification
func (sb *SpecBuilder) GetSpec() *OpenAPISpec {
	return sb.spec
}

// NewOperation creates a new operation
func NewOperation(summary, description, operationID string) *Operation {
	return &Operation{
		Summary:     summary,
		Description: description,
		OperationID: operationID,
		Responses:   make(map[string]Response),
	}
}

// NewSchema creates a new schema
func NewSchema(schemaType string) *Schema {
	return &Schema{
		Type:       schemaType,
		Properties: make(map[string]*Schema),
	}
}

// NewParameter creates a new parameter
func NewParameter(name, in, description string, required bool) *Parameter {
	return &Parameter{
		Name:        name,
		In:          in,
		Description: description,
		Required:    required,
		Schema:      NewSchema("string"),
	}
}

// AddProperty adds a property to a schema
func (s *Schema) AddProperty(name string, property *Schema) *Schema {
	if s.Properties == nil {
		s.Properties = make(map[string]*Schema)
	}
	s.Properties[name] = property
	s.Required = append(s.Required, name)
	return s
}

// AddResponse adds a response to an operation
func (op *Operation) AddResponse(code string, response Response) *Operation {
	if op.Responses == nil {
		op.Responses = make(map[string]Response)
	}
	op.Responses[code] = response
	return op
}

// AddParameter adds a parameter to an operation
func (op *Operation) AddParameter(param *Parameter) *Operation {
	if param != nil {
		op.Parameters = append(op.Parameters, *param)
	}
	return op
}

// SetRequestBody sets the request body for an operation
func (op *Operation) SetRequestBody(requestBody *RequestBody) *Operation {
	op.RequestBody = requestBody
	return op
}

// NewRequestBody creates a new request body
func NewRequestBody(description string, required bool) *RequestBody {
	return &RequestBody{
		Description: description,
		Required:    required,
		Content:     make(map[string]MediaType),
	}
}

// NewResponse creates a new response
func NewResponse(description string) Response {
	return Response{
		Description: description,
		Content:     make(map[string]MediaType),
		Headers:     make(map[string]Header),
	}
}

// RefSchema returns a reference to a schema
func RefSchema(name string) *Schema {
	return &Schema{
		Description: fmt.Sprintf("Reference to %s", name),
	}
}

// ArraySchema creates an array schema
func ArraySchema(items *Schema) *Schema {
	return &Schema{
		Type:  "array",
		Items: items,
	}
}

// StringEnum creates a string enum schema
func StringEnum(values ...string) *Schema {
	enums := make([]interface{}, len(values))
	for i, v := range values {
		enums[i] = v
	}
	return &Schema{
		Type: "string",
		Enum: enums,
	}
}
